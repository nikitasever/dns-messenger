"""
Tests for two admin-auth gaps found by a security scan and fixed in web_client.py:

1. /api/admin/logout used to bump the admin's global session-version (sv)
   with no auth check at all — any anonymous POST there kicked the real admin
   out, a no-auth-required denial of service against them.
2. admin_block() stopped a blocked user's poll loop but never invalidated
   their already-issued session cookie (get_messenger() only checks 'usv'),
   so a session opened before the block kept working — sending messages and
   files — until the server happened to restart.

Runs in an isolated temp directory so it never touches the repo's real
.messenger_admin.json / .messenger_sv.json / .messenger_blocked.json.

Run:  python tests/test_admin_auth.py
"""
import os
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"  [FAIL] {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  [ok] {name}")


def main():
    print("admin auth")

    prev = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:
        import web_client as wc
        wc.app.config['TESTING'] = True

        # Seed a known admin account (bypassing the random-password generation
        # in init_admin(), which is for first-run only).
        h, s = wc._hash_password('correct-horse')
        wc._save_json(wc.ADMIN_FILE, {'hash': h, 'salt': s, 'change_required': False, 'sv': 0})

        admin_client = wc.app.test_client()
        r = admin_client.post('/api/admin/login', json={'password': 'correct-horse'})
        check('admin logs in with the seeded password', r.get_json().get('ok') is True)

        # ── #14: unauthenticated /api/admin/logout must not touch admin sv ──
        sv_before = wc._load_json(wc.ADMIN_FILE)['sv']
        anon_client = wc.app.test_client()          # separate client: no session at all
        r = anon_client.post('/api/admin/logout')
        check('unauthenticated admin/logout still returns ok (no error leak)',
              r.get_json().get('ok') is True)
        sv_after = wc._load_json(wc.ADMIN_FILE)['sv']
        check('unauthenticated admin/logout does NOT bump the global admin sv',
              sv_after == sv_before)

        # The real admin's session must still be valid — prove it by calling
        # an is_admin-gated route.
        r = admin_client.get('/api/admin/users')
        check("the real admin's session survives the anonymous logout call",
              r.get_json().get('ok') is True)

        # A logout from the actual admin session must still work (not broken
        # by the fix).
        r = admin_client.post('/api/admin/logout')
        check('the real admin can still log themself out',
              r.get_json().get('ok') is True)
        sv_after_real = wc._load_json(wc.ADMIN_FILE)['sv']
        check('a genuine admin logout DOES bump sv', sv_after_real == sv_before + 1)
        r = admin_client.get('/api/admin/users')
        check("admin's own session is rejected after their own logout",
              r.get_json().get('ok') is not True)

        # ── #15: admin_block must invalidate an already-issued session ──────
        # Re-login as admin for the block call.
        admin_client2 = wc.app.test_client()
        admin_client2.post('/api/admin/login', json={'password': 'correct-horse'})

        # Simulate an already-authenticated victim session without needing a
        # live relay: stamp the session directly, the same shape api_login
        # leaves behind, and register a stand-in messenger object.
        victim = wc.app.test_client()
        with victim.session_transaction() as sess:
            sess['username'] = 'victim'
            sess['usv'] = wc.current_user_sv('victim')
        with wc.users_lock:
            wc.users['victim'] = SimpleNamespace(username='victim', running=True)

        r = victim.get('/api/me')
        check('victim session is authenticated before any block',
              r.get_json() == {'logged_in': True, 'username': 'victim'})

        r = admin_client2.post('/api/admin/block', json={'username': 'victim'})
        check('admin block call succeeds', r.get_json().get('ok') is True)

        r = victim.get('/api/me')
        check("victim's pre-existing session is invalidated immediately by the block "
              "(no server restart needed)",
              r.get_json().get('logged_in') is False)

        # A blocked user must also be unable to log back in.
        r = victim.post('/api/login', json={'username': 'victim', 'mode': 'anonymous'})
        check('a blocked user cannot log back in either',
              r.get_json().get('ok') is False)
    finally:
        os.chdir(prev)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
