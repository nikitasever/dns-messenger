"""
CSRF protection test. Unlike the other endpoint tests, this one deliberately
leaves TESTING = False so the before_request CSRF guard is actually enforced
(the guard is bypassed under TESTING so the pre-existing suite, which posts
without tokens, keeps working).

Verifies: every page carries a session-bound csrf token in a <meta> tag; a
mutating request without a valid X-CSRF-Token is rejected 403; the correct
token passes; GET stays exempt.

Runs in an isolated temp dir so it never touches repo state files.

Run:  python tests/test_csrf.py
"""
import os
import re
import sys
import tempfile

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
    print("csrf")

    prev = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:
        import web_client as wc
        # Enforcement is on precisely because we do NOT enable TESTING.
        check('CSRF is enforced (TESTING is off)', not wc.app.config.get('TESTING'))

        client = wc.app.test_client()

        # 1. The login page (unauthenticated) carries a csrf-token meta tag.
        r = client.get('/')
        html = r.get_data(as_text=True)
        m = re.search(r'<meta name="csrf-token" content="([^"]+)">', html)
        check('login page carries a csrf-token meta tag', bool(m))
        page_token = m.group(1) if m else ''
        check('the token looks like a real token (>20 chars)', len(page_token) > 20)

        # 2. It matches the token stored in the session.
        with client.session_transaction() as sess:
            sess_token = sess.get('csrf')
        check('meta token matches the session token', sess_token == page_token)

        # 3. A mutating request with no token is rejected 403.
        r = client.post('/api/logout')
        check('POST without X-CSRF-Token -> 403', r.status_code == 403)
        check('the 403 body names CSRF', 'CSRF' in (r.get_json() or {}).get('error', ''))

        # 4. A wrong token is rejected too.
        r = client.post('/api/logout', headers={'X-CSRF-Token': 'not-the-real-token'})
        check('POST with a wrong token -> 403', r.status_code == 403)

        # 5. The correct token passes the CSRF gate (handler runs; not a 403).
        r = client.post('/api/logout', headers={'X-CSRF-Token': page_token})
        check('POST with the correct token passes the CSRF gate', r.status_code != 403)

        # 6. Safe methods are exempt — GET needs no token.
        r = client.get('/api/me')
        check('GET is exempt from CSRF', r.status_code == 200)

        # 7. A brand-new client (no prior GET) is still challenged on POST.
        fresh = wc.app.test_client()
        r = fresh.post('/api/push/test')
        check('a fresh client POST is challenged 403', r.status_code == 403)
    finally:
        os.chdir(prev)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
