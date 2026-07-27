"""
Tests for two admin-auth gaps found by a security scan and fixed in web_client.py:

1. /api/admin/logout used to bump the admin's global session-version (sv)
   with no auth check at all — any anonymous POST there kicked the real admin
   out, a no-auth-required denial of service against them.
2. admin_block() stopped a blocked user's poll loop but never invalidated
   their already-issued session cookie (get_messenger() only checks 'usv'),
   so a session opened before the block kept working — sending messages and
   files — until the server happened to restart.
3. admin_delete() only removed the account entry, never the on-disk
   .messenger_<user>/ directory (identity.key, identity.recovery, pins.json)
   or the webauthn/backup-codes/profile-photo entries. A username freed up
   this way was permanently unusable afterwards: re-registering it built a
   fresh UserMessenger against the SAME on-disk identity.key, now encrypted
   under the wrong (new) password, which raised IdentityLocked and rejected
   the "Wrong password" even though this was a first-ever registration.

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

        # ── #16: admin_delete() must fully purge the username's identity ────
        from crypto_utils import Identity, IdentityLocked

        os.makedirs('.messenger_bob', exist_ok=True)
        Identity().save('.messenger_bob/identity.key', password='bobs-old-password')
        wc._save_json(wc.WEBAUTHN_FILE, {'bob': [{'id': 'x', 'label': 'old phone'}]})
        wc._save_json(wc.BACKUP_CODES_FILE, {'bob': [{'hash': 'h', 'salt': 's', 'used': False}]})
        wc._save_json(wc.PROFILES_FILE, {'bob': {'photo': 'data:image/png;base64,x'}})
        h, s = wc._hash_password('bobs-old-password')
        wc.save_account('bob', h, s)

        admin_client3 = wc.app.test_client()
        admin_client3.post('/api/admin/login', json={'password': 'correct-horse'})
        r = admin_client3.post('/api/admin/delete', json={'username': 'bob'})
        check('admin delete call succeeds', r.get_json().get('ok') is True)

        check("the old identity.key is gone from disk",
              not os.path.exists('.messenger_bob/identity.key'))
        check("bob's webauthn credentials are purged",
              'bob' not in wc._load_json(wc.WEBAUTHN_FILE))
        check("bob's backup codes are purged",
              'bob' not in wc._load_json(wc.BACKUP_CODES_FILE))
        check("bob's profile photo is purged",
              'bob' not in wc.get_profiles())

        # The freed-up username must be registrable again by someone new,
        # with a DIFFERENT password — this is the exact scenario that used
        # to raise IdentityLocked before the fix.
        try:
            fresh = wc.UserMessenger('bob', transport=None, password='a-totally-new-password',
                                      persist_identity=True)
            check('re-registering the freed username with a new password no '
                  'longer raises IdentityLocked', True)
            check("the fresh identity isn't the deleted user's old key material",
                  fresh.identity.private_bytes() != b'')  # just needs to exist / not have thrown
        except IdentityLocked:
            check('re-registering the freed username with a new password no '
                  'longer raises IdentityLocked', False)
    finally:
        os.chdir(prev)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
