"""
Integration test for group sender authentication through the real message path.

Spins up an in-process RelayServer and drives actual UserMessenger instances
(the same code the web app uses) so send_group / poll_group, the signing
context, key pinning and verify-key lookup are all exercised together — not
just the crypto primitives.

Scenario: alice creates a group with bob and mallory. A genuine message from
alice must verify; a message mallory forges with from='alice' (possible because
all three share the group key) must be caught as 'forged'.

Run:  python tests/test_group_auth.py
"""
import os
import socket
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import protocol  # noqa: E402
from protocol import (  # noqa: E402
    CMD_GROUP_SEND, CMD_GROUP_INVITE, CMD_GROUP_POLL,
    MAX_LABEL_LEN, b32encode, chunk_string,
)
from crypto_utils import encrypt, build_signed  # noqa: E402
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
    print("group_auth")
    DOMAIN = 'msg.test.local'
    port, srv = start_relay(DOMAIN)

    # UserMessenger writes .messenger_<user>/ in CWD — isolate in a temp dir
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
        gid = 'secretroom'

        check('alice creates the group', alice.create_group(gid))
        check('alice invites bob', alice.invite_to_group(gid, 'bob')['ok'])
        check('alice invites mallory', alice.invite_to_group(gid, 'mallory')['ok'])

        # bob and mallory pull the group + shared key
        bob.fetch_groups(); mallory.fetch_groups()
        check('bob received the group key', gid in bob.group_keys)
        check('mallory received the group key', gid in mallory.group_keys)

        # ── genuine message from alice ─────────────────────────────────
        check('alice sends a genuine group message', alice.send_group(gid, 'sortie at dawn'))
        got = bob.poll_group(gid)
        genuine = [m for m in got if m['text'] == 'sortie at dawn']
        check('bob receives the genuine message', len(genuine) == 1)
        check('genuine message is verified', genuine[0]['auth'] == 'verified')
        check('genuine message is attributed to alice', genuine[0]['from'] == 'alice')

        # ── mallory forges a message as alice ──────────────────────────
        # She has the group key, so she can encrypt; she sets from='alice'.
        # But she signs with HER Ed25519 key — that is what betrays her.
        gk = mallory.group_keys[gid]
        ctx = b'alice\x00' + gid.encode()          # context claims sender=alice
        forged_ct = encrypt(build_signed(mallory.identity, ctx, b'retreat now'), gk)
        data_b32 = b32encode(forged_ct)
        # send raw with from='alice'
        labels = [CMD_GROUP_SEND, gid, 'alice', protocol.gen_msg_id(), '0', '1'] + \
            chunk_string(data_b32, MAX_LABEL_LEN)
        mallory._q(labels)

        got = bob.poll_group(gid)
        forged = [m for m in got if m['text'] == 'retreat now']
        check('bob receives the forged message body', len(forged) == 1)
        check('forged message is flagged, not trusted', forged[0]['auth'] == 'forged')
        check('genuine vs forged are distinguishable',
              genuine[0]['auth'] == 'verified' and forged[0]['auth'] == 'forged')

        # ── mallory forges as alice WITHOUT a signature ────────────────
        # She encrypts raw plaintext (no build_signed) so open_signed returns
        # 'unsigned'. Pre-fix this rendered with no warning (impersonation);
        # the receiver must now treat any non-'verified' group message as forged.
        unsigned_ct = encrypt(b'stand down', gk)          # no signature framing
        labels = [CMD_GROUP_SEND, gid, 'alice', protocol.gen_msg_id(), '0', '1'] + \
            chunk_string(b32encode(unsigned_ct), MAX_LABEL_LEN)
        mallory._q(labels)
        got = bob.poll_group(gid)
        unsigned = [m for m in got if m['text'] == 'stand down']
        check('bob receives the unsigned forgery body', len(unsigned) == 1)
        check('an UNSIGNED group message is flagged forged, not trusted',
              unsigned[0]['auth'] == 'forged')

        # ── G1: cross-group replay of a sealed group key must fail ─────
        # The ECDH secret between alice and bob is the same for every group
        # they share, so a relay that swaps which gid a sealed-key blob is
        # served under would (without gid-bound AAD) hand bob a key he'd
        # accept for the wrong room. Simulate the swap server-side and
        # confirm unseal now fails (gid is authenticated data).
        gid2 = 'anotherroom'
        check('alice creates a second group', alice.create_group(gid2))
        check('alice invites bob to the second group', alice.invite_to_group(gid2, 'bob')['ok'])
        # Swap gid2's stored key entry for bob with gid's (secretroom) entry —
        # same sender, same ciphertext, wrong room — simulating an untrusted
        # relay that replays an old sealed-key blob under a different group.
        with srv.lock:
            srv.groups[gid2]['keys']['bob'] = dict(srv.groups[gid]['keys']['bob'])
        bob.group_keys.pop(gid2, None)
        bob.fetch_groups()
        check('replayed cross-group key blob is rejected', gid2 not in bob.group_keys)

        # ── G3: forged 'inviter' claim is rejected (relay-level auth) ───
        # Pre-fix, _h_ginvite trusted the claimed inviter name with only a
        # membership check (no proof of key ownership) — anyone could invite
        # arbitrary users into a group "as" any existing member. Mallory (a
        # real member of secretroom, but not alice) tries to invite 'eve'
        # while claiming to be alice, with a garbage signature.
        garbage_sig_b32 = b32encode(b'\x00' * 64)
        fake_key_b32 = b32encode(b'irrelevant-key-bytes')
        labels = [CMD_GROUP_INVITE, gid, 'alice', 'eve'] + chunk_string(
            garbage_sig_b32 + fake_key_b32, MAX_LABEL_LEN)
        resp = mallory._q(labels)
        check('forged-inviter ginvite is rejected', resp.startswith('ERR'))
        with srv.lock:
            check('eve was never added as a member', 'eve' not in srv.groups[gid]['members'])

        # ── G3: forged 'user' claim on gpoll is rejected ────────────────
        # Pre-fix, _h_gpoll trusted the claimed polling user with only a
        # membership check — anyone could mark bob's group messages "read"
        # on his behalf (delivery theft) without proving they are bob.
        alice.send_group(gid, 'second sortie')
        labels = [CMD_GROUP_POLL, gid, 'bob', '0']   # unsigned, claims to be bob
        resp = mallory._q(labels)
        check('forged-user gpoll is rejected', resp.startswith('ERR'))
        got = bob.poll_group(gid)
        second = [m for m in got if m['text'] == 'second sortie']
        check("bob still receives the message mallory tried to steal-read", len(second) == 1)

        sock_stop = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_stop.sendto(b'stop', ('127.0.0.1', port))
    finally:
        os.chdir(prev_cwd)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
