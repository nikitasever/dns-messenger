"""
Integration test for the Double Ratchet DM path (Phase 1 of docs/ratchet-plan.md).

Spins up an in-process RelayServer and drives actual UserMessenger instances
(the same code the web app uses) so send_dm / poll_dm, prekey bootstrap/
publish/consume, the X3DH handshake and the wire-format branching (legacy
static vs ratchet-init vs ratchet-continue) are all exercised together — not
just the ratchet.py primitives in isolation (see test_ratchet.py for that).

Scenario: alice and bob are both registered (have prekeys); mallory logs in
anonymously (no prekeys at all, permanent legacy fallback). Confirms:
- alice's first message to bob is carried by the RATCHET_INIT wire scheme
  and consumes exactly one of bob's published one-time prekeys;
- the conversation continues on RATCHET_CONT afterwards;
- messages are readable, correctly attributed, and 'verified' throughout;
- an anonymous participant (no prekeys) falls back to the legacy scheme with
  no crash and no silent security downgrade for the OTHER side of unrelated
  conversations;
- restarting alice's UserMessenger (simulating a server restart) transparently
  RECOVERS the ratchet session from disk (Phase 2: persistence) — bob's next
  message decrypts correctly with no re-handshake needed. See
  test_ratchet_persistence.py for the focused unit-level version of this; the
  wrong-password case (an attacker or a mistyped password must NOT recover
  someone else's session) is also covered there.

Run:  python tests/test_dm_ratchet.py
"""
import os
import socket
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import RelayServer                # noqa: E402
from transport import UDPTransport             # noqa: E402

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
    return port


def main():
    print("dm_ratchet")
    DOMAIN = 'msg.test.local'
    port = start_relay(DOMAIN)

    prev_cwd = os.getcwd()
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)
    try:
        import web_client
        UM = web_client.UserMessenger

        def mk(name, password=None):
            m = UM(name, UDPTransport('127.0.0.1', port, DOMAIN), password=password,
                   persist_identity=password is not None)
            m.register()
            return m

        alice = mk('alice', password='alice-password-123')
        bob = mk('bob', password='bob-password-456')

        check('alice bootstrapped her own prekeys', alice.prekeys is not None)
        check('bob bootstrapped his own prekeys', bob.prekeys is not None)
        bundles = web_client.get_prekey_bundles()
        check("bob's public bundle got published", 'bob' in bundles)
        otpk_before = len(bundles['bob']['one_time'])
        check('bob published a full pool of one-time prekeys',
              otpk_before == web_client.ONE_TIME_PREKEY_POOL_TARGET)

        # alice needs bob's identity/verify key pinned before send_dm can even
        # attempt X3DH (same prerequisite the legacy path always had).
        check("alice resolves bob's identity key", alice.get_peer_key('bob') is not None)
        # bob must resolve alice's key too, or send_dm's peer_verify lookup
        # (needed to verify bob's OWN signed prekey isn't relevant here, but
        # alice verifying BOB's signed prekey needs alice to know bob's
        # verify key too — get_peer_key already pinned it above).

        # ── alice's first message to bob: must use X3DH + ratchet init ──────
        res = alice.send_dm('bob', 'hello bob, this is alice')
        check('send_dm reports ok for the first (X3DH) message', res['ok'])
        check("alice's ratchet session with bob now exists", 'bob' in alice.ratchets)

        bundles_after = web_client.get_prekey_bundles()
        check("bob's one-time prekey pool shrank by exactly one after alice's handshake",
              len(bundles_after['bob']['one_time']) == otpk_before - 1)

        got = bob.poll_dm()
        genuine = [m for m in got if m['text'] == 'hello bob, this is alice']
        check('bob receives and decrypts the ratchet-init message', len(genuine) == 1)
        check('the message is attributed to alice and verified',
              genuine[0]['from'] == 'alice' and genuine[0]['auth'] == 'verified')
        check("bob's ratchet session with alice now exists (created on receipt)",
              'alice' in bob.ratchets)
        check("the one-time prekey bob's side consumed is gone from HIS private pool too",
              len(bob.prekeys['one_time']) == web_client.ONE_TIME_PREKEY_POOL_TARGET - 1)

        # ── conversation continues on RATCHET_CONT both directions ──────────
        res = bob.send_dm('alice', 'hi alice, bob here')
        check("bob's reply send_dm succeeds", res['ok'])
        got = alice.poll_dm()
        reply = [m for m in got if m['text'] == 'hi alice, bob here']
        check("alice receives bob's reply", len(reply) == 1)
        check("bob's reply is verified", reply[0]['auth'] == 'verified')

        res = alice.send_dm('bob', 'glad that worked')
        check('a second message from alice (pure ratchet-continue) succeeds', res['ok'])
        got = bob.poll_dm()
        second = [m for m in got if m['text'] == 'glad that worked']
        check("bob receives alice's second message", len(second) == 1)

        # ── anonymous participant: no prekeys, must fall back cleanly ───────
        mallory = mk('mallory')  # no password => anonymous, persist_identity=False
        check('an anonymous user has no prekeys', mallory.prekeys is None)
        check("bob resolves mallory's identity key", bob.get_peer_key('mallory') is not None)
        res = bob.send_dm('mallory', 'are you there')
        check('bob can still message an anonymous user (legacy fallback)', res['ok'])
        got = mallory.poll_dm()
        anon_msg = [m for m in got if m['text'] == 'are you there']
        check('the anonymous user receives and decrypts the fallback message',
              len(anon_msg) == 1 and anon_msg[0]['auth'] == 'verified')
        # This must NOT have touched bob's ratchet sessions with anyone else.
        check("bob/alice's ratchet session is untouched by the unrelated anon conversation",
              'alice' in bob.ratchets)

        # ── Phase 2: a server restart no longer loses the session ───────────
        # A fresh UserMessenger object (same on-disk state, same password) is
        # exactly what a real restart produces (see _restore_messenger).
        alice_restarted = UM('alice', UDPTransport('127.0.0.1', port, DOMAIN),
                              password='alice-password-123', persist_identity=True)
        check("the restarted alice object recovers her ratchet session with bob "
              "from disk", 'bob' in alice_restarted.ratchets)
        res = bob.send_dm('alice', 'are you still there after the restart')
        check("bob's send still succeeds", res['ok'])
        got = alice_restarted.poll_dm()
        after_restart = [m for m in got if m['text'] == 'are you still there after the restart']
        check('the restarted side decrypts a NEW message correctly with no '
              're-handshake needed', len(after_restart) == 1)
        check("it's verified, not just decrypted", after_restart[0]['auth'] == 'verified')

        print(f"\n{passed} passed")
    finally:
        os.chdir(prev_cwd)


if __name__ == '__main__':
    main()
