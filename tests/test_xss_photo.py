"""
Regression test for the profile-photo stored XSS, proven live in a real
Chrome tab: a crafted `photo` value broke out of <img src="..."> and set
document.title to "XSS-PWNED" via onerror, purely through the app's normal
flow (upload as one account, view as another whose chat rendered the avatar).

This test hits the real /api/profile/photo endpoint with the exact payload
that fired live, proving the server now rejects it, plus a battery of shaped
variants and confirms legitimate canvas.toDataURL()-style uploads still work.

Runs in an isolated temp dir so it never touches the repo's real
.messenger_profiles.json. Session is stamped directly (same technique as
test_admin_auth.py) since no live relay is needed to test this endpoint.

Run:  python tests/test_xss_photo.py
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
    print("xss photo")

    prev = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:
        import web_client as wc
        wc.app.config['TESTING'] = True

        client = wc.app.test_client()
        with client.session_transaction() as sess:
            sess['username'] = 'user1'
            sess['usv'] = wc.current_user_sv('user1')
        with wc.users_lock:
            wc.users['user1'] = SimpleNamespace(username='user1', running=True)

        def set_photo(photo):
            return client.post('/api/profile/photo', json={'photo': photo}).get_json()

        # The exact payload that fired live in a real browser before the fix.
        exploit = ('data:image/png,x" onerror="window.__xss_fired='
                   '(window.__xss_fired||0)+1; document.title=\'XSS-PWNED\'"')
        r = set_photo(exploit)
        check('the exact live-fired exploit payload is now rejected',
              r.get('ok') is False)

        # Shaped variants — the vulnerability wasn't specific to one payload.
        variants = [
            'data:image/png,x" onerror="alert(1)"',
            "data:image/png,x' onmouseover='alert(1)",
            'data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=',   # SVG carries its own script capability
            'data:text/html;base64,PHNjcmlwdD4=',            # wrong MIME entirely
            'data:image/png;base64,not valid base64!!',      # non-base64 chars after the comma
            'javascript:alert(1)',
            '<img src=x onerror=alert(1)>',
        ]
        for v in variants:
            r = set_photo(v)
            check(f'rejected: {v[:50]!r}', r.get('ok') is False)

        # Legitimate uploads (what canvas.toDataURL('image/jpeg', 0.8) and a
        # real PNG actually produce) must keep working.
        legit = [
            'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wA=',
            'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB=',
            '',   # clearing the photo
        ]
        for v in legit:
            r = set_photo(v)
            check(f'accepted (legitimate): {v[:40]!r}', r.get('ok') is True)

        # Confirm the accepted photo is actually what gets served back.
        set_photo('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB=')
        r = client.get('/api/profile/photo/user1').get_json()
        check('stored legitimate photo round-trips through the getter',
              r['photo'] == 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB=')
    finally:
        os.chdir(prev)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
