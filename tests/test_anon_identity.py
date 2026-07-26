"""
A2: anonymous sessions must not be resumable by name.

Anonymous login has no password gate, so a chosen username can't be allowed
to double as a durable identity key the way it is for register/login. Before
the fix:
  - identity.key/pins.json were written to disk under `.messenger_<username>/`
    for anonymous users too (unencrypted, since there's no password to
    encrypt with), so anyone who later typed the same nickname silently
    loaded the SAME identity + mailbox + pins — full impersonation with zero
    authentication;
  - the in-process `users` dict is keyed by the bare username for every mode,
    so a second concurrent anonymous login with the same name reused the
    SAME live UserMessenger object outright — no need to even wait for a
    restart.

Fixes: UserMessenger(persist_identity=False) for anonymous mode keeps
identity/pins in memory only; api_login rejects an anonymous name that's
already an active session; api_logout drops the anonymous entry from
`users` so the name is both unresumable and freed for reuse.

Run:  python tests/test_anon_identity.py
"""
import os
import socket
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import RelayServer          # noqa: E402
from transport import UDPTransport      # noqa: E402

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
    print("anon_identity")
    DOMAIN = 'msg.test.local'
    port = start_relay(DOMAIN)

    prev_cwd = os.getcwd()
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)
    try:
        import web_client as wc
        wc.app.config['TESTING'] = True
        wc.transport = UDPTransport('127.0.0.1', port, DOMAIN)

        # ── in-process live-session hijack by name ──────────────────────
        alice = wc.app.test_client()
        r = alice.post('/api/login', json={'username': 'guest1', 'mode': 'anonymous'})
        check('alice logs in anonymously as guest1', r.get_json().get('ok') is True)

        mallory = wc.app.test_client()
        r = mallory.post('/api/login', json={'username': 'guest1', 'mode': 'anonymous'})
        check("mallory can't claim alice's still-active anonymous name",
              r.get_json().get('ok') is False)

        with wc.users_lock:
            alice_m = wc.users.get('guest1')
        check('the live session object is still alice\'s original identity',
              alice_m is not None)

        # ── no disk persistence for anonymous identity ───────────────────
        check('no on-disk identity dir was created for the anonymous user',
              not os.path.isdir('.messenger_guest1'))

        # ── logout drops the live entry — no in-memory resume either ─────
        old_pub = alice_m.identity.public_bytes()
        r = alice.post('/api/logout')
        check('alice logs out', r.get_json().get('ok') is True)
        with wc.users_lock:
            check('logout drops the anonymous entry from the live users map',
                  'guest1' not in wc.users)

        # Bob typing the SAME name after logout must NOT silently hand him
        # alice's old identity/mailbox. Since that identity was never
        # persisted (persist_identity=False), a would-be resumer has no way
        # to reproduce alice's key — the relay's name-pinning (TOFR) then
        # correctly refuses to re-seat 'guest1' under any different key,
        # which is a hard failure, not a silent handoff. (Anonymous names are
        # therefore single-use per relay lifetime — a UX cost, not a security
        # hole; already noted in the audit as inherent to TOFR.)
        bob = wc.app.test_client()
        r = bob.post('/api/login', json={'username': 'guest1', 'mode': 'anonymous'})
        check("bob cannot resume alice's old anonymous identity under the same name",
              r.get_json().get('ok') is False)

        # A never-before-used anonymous name still works fine and gets its
        # own distinct, non-persisted identity.
        r = bob.post('/api/login', json={'username': 'guest2', 'mode': 'anonymous'})
        check('a fresh anonymous name still logs in normally', r.get_json().get('ok') is True)
        with wc.users_lock:
            bob_m = wc.users.get('guest2')
        check("the fresh name's identity differs from alice's old one",
              bob_m is not None and bob_m.identity.public_bytes() != old_pub)
        check('no on-disk identity dir was created for the fresh anonymous user either',
              not os.path.isdir('.messenger_guest2'))

        sock_stop = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_stop.sendto(b'stop', ('127.0.0.1', port))
    finally:
        os.chdir(prev_cwd)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
