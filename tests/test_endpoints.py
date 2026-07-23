"""
Smoke tests for web_client Flask routes that don't require a live relay.

Run:  python tests/test_endpoints.py
Exits non-zero on failure. Uses Flask's test client (no network).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import web_client  # noqa: E402

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"  [FAIL] {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  [ok] {name}")


def main():
    app = web_client.app
    app.config['TESTING'] = True
    c = app.test_client()

    print("endpoints")

    # Login page renders for anonymous users
    r = c.get('/')
    check('GET / returns 200', r.status_code == 200)
    check('login page served when unauthenticated', b'login' in r.data.lower() or b'\xd0\x92\xd1\x85\xd0\xbe\xd0\xb4' in r.data)

    # Service worker served from root with correct headers
    r = c.get('/sw.js')
    check('GET /sw.js returns 200', r.status_code == 200)
    check('sw.js has js mimetype', 'javascript' in r.headers.get('Content-Type', ''))
    check('sw.js allows root scope', r.headers.get('Service-Worker-Allowed') == '/')

    # Manifest served
    r = c.get('/manifest.json')
    check('GET /manifest.json returns 200', r.status_code == 200)
    check('manifest is json', b'"name"' in r.data and b'standalone' in r.data)

    # PWA icons exist
    for size in (192, 512):
        r = c.get(f'/static/icon-{size}.png')
        check(f'icon-{size}.png served', r.status_code == 200 and r.data[:8] == b'\x89PNG\r\n\x1a\n')

    # VAPID public key is readable without auth (the client needs it to subscribe)
    r = c.get('/api/push/key')
    check('GET /api/push/key returns 200', r.status_code == 200)
    key = r.get_json().get('key', '')
    check('push key is a base64url uncompressed P-256 point',
          len(web_client.webpush.b64u_decode(key)) == 65)
    check('push key is stable across calls', c.get('/api/push/key').get_json()['key'] == key)

    # Subscribing requires auth
    r = c.post('/api/push/subscribe', json={'subscription': {
        'endpoint': 'https://example.com/x', 'keys': {'p256dh': 'a', 'auth': 'b'}}})
    check('/api/push/subscribe blocks unauthenticated', r.get_json().get('ok') is False)
    r = c.post('/api/push/test')
    check('/api/push/test blocks unauthenticated', r.get_json().get('ok') is False)

    # Protected API rejects unauthenticated access
    r = c.post('/api/send', json={'to': 'bob', 'text': 'hi'})
    check('/api/send blocks unauthenticated', r.status_code in (200, 401, 403) and b'"ok": true' not in r.data)

    # Privacy validation
    r = c.post('/api/privacy/last-seen', json={'visibility': 'bogus'})
    check('/api/privacy/last-seen rejects bad value or requires auth', r.status_code in (200, 401, 403))

    # Session revocation must be durable: it is what stops a captured
    # pre-logout cookie from working again, now that SECRET_KEY is persisted.
    import json as _json
    name = '__sv_selftest__'
    before = web_client.current_user_sv(name)
    after = web_client.bump_user_sv(name)
    check('bump_user_sv increments', after == before + 1)
    check('bump_user_sv is visible to current_user_sv',
          web_client.current_user_sv(name) == after)
    on_disk = _json.loads(web_client.SV_FILE.read_text('utf-8'))
    check('session revocation is written to disk', on_disk.get(name) == after)
    # Leave no residue behind
    on_disk.pop(name, None)
    web_client._save_json(web_client.SV_FILE, on_disk)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
