"""
Group leave/kick + re-key (Phase 4 of docs/ratchet-plan.md).

Same shape as test_group_auth.py: a real in-process RelayServer driven by
actual UserMessenger instances, so signing, relay-side membership checks,
and the client's key-rotation/pickup logic (fetch_groups/check_group_rekey)
are all exercised together, not just isolated primitives.

Scenario: alice creates a group with bob and mallory. Mallory is kicked;
alice's group key must rotate and mallory's old key must no longer decrypt
new traffic. Separately, bob leaves voluntarily and alice (sole remaining
member, deterministic elector) re-keys on the next check_group_rekey tick.

Run:  python tests/test_group_rekey.py
"""
import os
import socket
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import protocol  # noqa: E402
from protocol import CMD_GROUP_LEAVE, CMD_GROUP_KICK, b32encode, b32decode, chunk_string, MAX_LABEL_LEN  # noqa: E402
from server import RelayServer  # noqa: E402
from transport import UDPTransport  # noqa: E402

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"  [FAIL] {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  [ok] {name}")


def start_relay(domain):
    srv = RelayServer(domain, bind='127.0.0.1', port=0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]

    def serve():
        while True:
            data, addr = sock.recvfrom(4096)
            if data == b'stop':
                break
            sock.sendto(srv.handle_query(data), addr)

    threading.Thread(target=serve, daemon=True).start()
    return port, srv


def main():
    print("group rekey (leave/kick)")
    DOMAIN = 'msg.test.local'
    port, srv = start_relay(DOMAIN)

    prev_cwd = os.getcwd()
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)
    try:
        import web_client
        UM = web_client.UserMessenger

        def mk(name):
            m = UM(name, UDPTransport('127.0.0.1', port, DOMAIN))
            m.register()
            return m

        alice, bob, mallory = mk('alice'), mk('bob'), mk('mallory')
        gid = 'warroom'

        check('alice creates the group', alice.create_group(gid))
        check('alice invites bob', alice.invite_to_group(gid, 'bob')['ok'])
        check('alice invites mallory', alice.invite_to_group(gid, 'mallory')['ok'])
        bob.fetch_groups(); mallory.fetch_groups()
        check('bob has the group key', gid in bob.group_keys)
        check('mallory has the group key', gid in mallory.group_keys)

        check('list_group_members reports all three',
              set(alice.list_group_members(gid)) == {'alice', 'bob', 'mallory'})

        # ── kick: alice removes mallory, key rotates synchronously ──────
        mallory_old_key = mallory.group_keys[gid]
        result = alice.kick_member(gid, 'mallory')
        check('kick reports ok', result['ok'])
        check("kick reports no delivery failures", result.get('rekey_failed') == [])
        with srv.lock:
            check('mallory removed from relay membership', 'mallory' not in srv.groups[gid]['members'])
        check("alice's local key rotated", alice.group_keys[gid] != mallory_old_key)

        bob.fetch_groups()
        check("bob picked up the rotated key", bob.group_keys[gid] == alice.group_keys[gid])

        check('alice sends after the kick', alice.send_group(gid, 'mallory is out'))
        got = bob.poll_group(gid)
        msg = [m for m in got if m['text'] == 'mallory is out']
        check('bob decrypts the post-kick message', len(msg) == 1)
        check('post-kick message verifies', msg and msg[0]['auth'] == 'verified')

        check("mallory can no longer poll the group (kicked)",
              mallory.poll_group(gid) == [] and
              mallory._q([protocol.CMD_GROUP_POLL, gid, 'mallory', '0']).startswith('ERR'))

        # Mallory's stale key must not decrypt the new traffic even if she
        # somehow still received ciphertext — this IS the forward-secrecy
        # property a kick is supposed to buy.
        from crypto_utils import decrypt as _decrypt
        raised = False
        try:
            last_ct = b32decode((srv.group_mail.get(gid) or [{'data': ''}])[-1]['data'])
            _decrypt(last_ct, mallory_old_key)
        except Exception:
            raised = True
        check("mallory's pre-kick key fails to decrypt post-kick traffic", raised)

        # ── kicking a non-member / self-kick are rejected ────────────────
        # Real, correctly-signed requests via the client method — a garbage
        # signature would fail auth before ever reaching these semantic
        # checks, which is a different (already-covered) failure mode.
        already_removed = alice.kick_member(gid, 'mallory')
        check('kicking an already-removed member is rejected', not already_removed['ok'])
        self_kick = alice.kick_member(gid, 'alice')
        check('self-kick is rejected (use leave)', self_kick.get('error') == 'ERR:use_leave')

        # ── forged kick: bob claims to be alice, garbage signature ──────
        garbage = chunk_string(b32encode(b'\x00' * 64), MAX_LABEL_LEN)
        resp = bob._q([CMD_GROUP_KICK, gid, 'alice', 'bob', 'nonce123', '9999999999'] + garbage)
        check('forged-kicker kick is rejected', resp.startswith('ERR'))
        with srv.lock:
            check('bob is still a member after the forged kick attempt', 'bob' in srv.groups[gid]['members'])

        # ── voluntary leave + decentralized re-key ───────────────────────
        # Only alice and bob remain; bob leaves. Neither leave_group nor the
        # relay push a new key — it's check_group_rekey's deterministic
        # elector (lexicographically-smallest remaining member) that must
        # notice the shrink and re-key on its own.
        bob_old_key = bob.group_keys[gid]
        check('bob leaves the group', bob.leave_group(gid))
        with srv.lock:
            check('bob removed from relay membership', 'bob' not in srv.groups[gid]['members'])

        # alice already has a _group_last_members baseline for this group
        # (rekey_group, called synchronously by the earlier kick, seeded it)
        # — so this single tick both sees the shrink from that baseline and
        # re-keys immediately, with no separate "seeding" round needed here.
        alice_key_before = alice.group_keys[gid]
        alice.check_group_rekey()
        check("alice (sole remaining member) re-keyed after bob's departure",
              alice.group_keys[gid] != alice_key_before)

        # A genuinely first-ever observation (no baseline yet) must NOT
        # rekey just because it's the first tick — only an actual shrink
        # relative to a previously-seen membership should trigger it.
        gid2 = 'freshroom'
        check('alice creates a second, untouched group', alice.create_group(gid2))
        check('alice invites bob to it', alice.invite_to_group(gid2, 'bob')['ok'])
        fresh_key = alice.group_keys[gid2]
        check('no prior baseline exists yet for the fresh group',
              gid2 not in alice._group_last_members)
        alice.check_group_rekey()
        check("first-ever observation doesn't spuriously rekey an unchanged group",
              alice.group_keys[gid2] == fresh_key)

        check("bob can no longer poll after leaving",
              bob._q([protocol.CMD_GROUP_POLL, gid, 'bob', '0']).startswith('ERR'))

        # ── forged leave: mallory claims to be alice ─────────────────────
        resp = mallory._q([CMD_GROUP_LEAVE, gid, 'alice', 'nonce456', '9999999999'] + garbage)
        check('forged leave is rejected', resp.startswith('ERR'))
        with srv.lock:
            check("alice wasn't removed by mallory's forged leave", 'alice' in srv.groups[gid]['members'])

        sock_stop = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_stop.sendto(b'stop', ('127.0.0.1', port))
    finally:
        os.chdir(prev_cwd)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
