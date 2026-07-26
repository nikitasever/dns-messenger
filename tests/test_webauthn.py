"""
WebAuthn (passkey) second factor, layered on top of register/login accounts.

Covers the wiring, not the cryptography itself (that's py_webauthn's job, and
it has its own test suite): password still gates identity, a passkey is only
ever an ADDITIONAL requirement, the session-granting tail
(fetch_groups/start_poll_loop/session['username']) never runs before both
factors pass, one user's registration-ceremony challenge can't complete under
another session, and anonymous accounts are excluded entirely (no password to
2FA on top of, and A2 already keeps anonymous identity out of persistent
storage, so a stored credential would never be checked at the next login).

verify_registration_response / verify_authentication_response are monkeypatched
to fake a real authenticator's response — that only proves attacker knowledge
of a private key an authenticator refuses to export, not something a unit
test can reproduce meaningfully.

Run:  python tests/test_webauthn.py
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
    print("webauthn")
    DOMAIN = 'msg.test.local'
    port = start_relay(DOMAIN)

    prev_cwd = os.getcwd()
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)
    try:
        import web_client as wc
        import webauthn
        from webauthn.registration.verify_registration_response import VerifiedRegistration
        from webauthn.authentication.verify_authentication_response import VerifiedAuthentication
        from webauthn.helpers.structs import AttestationFormat, PublicKeyCredentialType, CredentialDeviceType

        wc.app.config['TESTING'] = True
        wc.transport = UDPTransport('127.0.0.1', port, DOMAIN)

        FAKE_CRED_ID = b'\x01' * 32
        FAKE_PUB_KEY = b'\x02' * 77

        def fake_verify_registration_response(**kwargs):
            return VerifiedRegistration(
                credential_id=FAKE_CRED_ID, credential_public_key=FAKE_PUB_KEY,
                sign_count=0, aaguid='', fmt=AttestationFormat.NONE,
                credential_type=PublicKeyCredentialType.PUBLIC_KEY, user_verified=True,
                attestation_object=b'', credential_device_type=CredentialDeviceType.SINGLE_DEVICE,
                credential_backed_up=False,
            )

        def fake_verify_authentication_response(**kwargs):
            return VerifiedAuthentication(
                credential_id=FAKE_CRED_ID, new_sign_count=1,
                credential_device_type=CredentialDeviceType.SINGLE_DEVICE,
                credential_backed_up=False, user_verified=True,
            )

        # ── register a real account and log in once (no passkey yet) ────
        alice = wc.app.test_client()
        r = alice.post('/api/login', json={'username': 'alice', 'password': 'correct-horse-battery', 'mode': 'register'})
        check('alice registers', r.get_json().get('ok') is True)
        check('no 2FA prompt before any passkey exists', 'need_webauthn' not in r.get_json())
        check('/api/me confirms the session was granted directly',
              alice.get('/api/me').get_json().get('logged_in') is True)
        alice.post('/api/logout')

        # ── anonymous accounts are excluded even if they try the ceremony ─
        anon = wc.app.test_client()
        anon.post('/api/login', json={'username': 'guest9', 'mode': 'anonymous'})
        r = anon.post('/api/webauthn/register/options')
        check('anonymous sessions cannot start a passkey registration ceremony',
              r.status_code == 403 and r.get_json().get('ok') is False)
        anon.post('/api/logout')

        # ── log alice back in and enroll a passkey ───────────────────────
        alice = wc.app.test_client()
        r = alice.post('/api/login', json={'username': 'alice', 'password': 'correct-horse-battery', 'mode': 'login'})
        check('alice logs back in with just her password', r.get_json().get('ok') is True)

        r = alice.post('/api/webauthn/register/options')
        options = r.get_json()
        check('registration options carry a challenge and require UV',
              bool(options.get('challenge')) and
              options.get('authenticatorSelection', {}).get('userVerification') == 'required')

        webauthn.verify_registration_response = fake_verify_registration_response
        r = alice.post('/api/webauthn/register/verify',
                        json={'credential': {'id': 'x', 'rawId': 'x', 'type': 'public-key',
                                              'response': {'clientDataJSON': 'x', 'attestationObject': 'x'}},
                              'label': 'Test device'})
        reg_body = r.get_json()
        check('passkey registration verifies and stores the credential', reg_body.get('ok') is True)

        # ── the very first passkey auto-issues one-time backup codes ────
        backup_codes = reg_body.get('backup_codes')
        check('the first passkey enrollment auto-issues 10 backup codes',
              isinstance(backup_codes, list) and len(backup_codes) == 10)
        check('backup codes are formatted for readability (XXXXX-XXXXX)',
              all(len(c) == 11 and c[5] == '-' for c in backup_codes))
        check('backup codes are all distinct', len(set(backup_codes)) == 10)

        status = alice.get('/api/webauthn/backup-codes/status').get_json()
        check('status reports 10/10 right after issuance',
              status.get('remaining') == 10 and status.get('total') == 10)

        with wc.webauthn_lock:
            on_disk = wc._load_json(wc.BACKUP_CODES_FILE)['alice']
        check('only hashes are persisted, never the plaintext codes',
              all('hash' in e and 'plaintext' not in str(e) for e in on_disk) and
              not any(c.replace('-', '') in str(on_disk) for c in backup_codes))

        r = alice.get('/api/webauthn/credentials')
        creds = r.get_json().get('credentials', [])
        check('exactly one passkey is now on file', len(creds) == 1)
        check('the stored label round-trips', creds[0]['label'] == 'Test device')
        check('the raw public key is never exposed to the client', 'public_key' not in creds[0])
        cred_id = creds[0]['id']
        alice.post('/api/logout')

        # ── logging in now requires the second factor ───────────────────
        alice2 = wc.app.test_client()
        r = alice2.post('/api/login', json={'username': 'alice', 'password': 'correct-horse-battery', 'mode': 'login'})
        body = r.get_json()
        check('password-only login now reports need_webauthn instead of granting a session',
              body.get('ok') is True and body.get('need_webauthn') is True)
        check('no session was actually granted yet',
              alice2.get('/api/me').get_json().get('logged_in') is False)
        check("password-verified username can't reach a group-poll/DM endpoint pre-2FA either",
              alice2.post('/api/send', json={'to': 'bob', 'text': 'hi'}).get_json().get('ok') is False)

        # A second, unrelated client (no password verified) can't start or
        # finish the passkey ceremony just by knowing it should exist.
        stranger = wc.app.test_client()
        r = stranger.post('/api/webauthn/login/options')
        check("a client that never passed the password step can't request an assertion challenge",
              r.status_code == 401)

        r = alice2.post('/api/webauthn/login/options')
        auth_options = r.get_json()
        check('authentication options list the enrolled credential and require UV',
              any(c['id'] == cred_id for c in auth_options.get('allowCredentials', [])) and
              auth_options.get('userVerification') == 'required')

        webauthn.verify_authentication_response = fake_verify_authentication_response
        r = alice2.post('/api/webauthn/login/verify',
                         json={'credential': {'id': cred_id, 'rawId': cred_id, 'type': 'public-key',
                                               'response': {'clientDataJSON': 'x', 'authenticatorData': 'x',
                                                             'signature': 'x', 'userHandle': None}}})
        check('the second factor completes the login', r.get_json().get('ok') is True)
        check('the session is now actually granted',
              alice2.get('/api/me').get_json().get('logged_in') is True)

        with wc.webauthn_lock:
            stored = wc._load_json(wc.WEBAUTHN_FILE)['alice'][0]
        check('the sign counter was updated from the authenticator response', stored['sign_count'] == 1)

        # ── an unknown credential id is rejected ─────────────────────────
        alice3 = wc.app.test_client()
        alice3.post('/api/login', json={'username': 'alice', 'password': 'correct-horse-battery', 'mode': 'login'})
        alice3.post('/api/webauthn/login/options')
        r = alice3.post('/api/webauthn/login/verify',
                         json={'credential': {'id': 'not-a-real-credential', 'rawId': 'not-a-real-credential',
                                               'type': 'public-key',
                                               'response': {'clientDataJSON': 'x', 'authenticatorData': 'x',
                                                             'signature': 'x'}}})
        check('an unrecognized credential id is rejected outright',
              r.get_json().get('ok') is False)
        check("the failed attempt didn't leave a stray session either",
              alice3.get('/api/me').get_json().get('logged_in') is False)

        # ── logging in with a backup code instead of the passkey ────────
        stranger2 = wc.app.test_client()
        r = stranger2.post('/api/webauthn/login/backup', json={'code': backup_codes[0]})
        check("a client that never passed the password step can't redeem a backup code either",
              r.status_code == 401)

        alice5 = wc.app.test_client()
        alice5.post('/api/login', json={'username': 'alice', 'password': 'correct-horse-battery', 'mode': 'login'})
        r = alice5.post('/api/webauthn/login/backup', json={'code': backup_codes[0]})
        check('a valid, unused backup code logs in without touching the passkey ceremony',
              r.get_json().get('ok') is True)
        check('the session is granted', alice5.get('/api/me').get_json().get('logged_in') is True)

        status = alice5.get('/api/webauthn/backup-codes/status').get_json()
        check('one code being consumed drops remaining to 9 (still 10 total)',
              status.get('remaining') == 9 and status.get('total') == 10)

        alice6 = wc.app.test_client()
        alice6.post('/api/login', json={'username': 'alice', 'password': 'correct-horse-battery', 'mode': 'login'})
        r = alice6.post('/api/webauthn/login/backup', json={'code': backup_codes[0]})
        check('the same backup code cannot be redeemed twice',
              r.get_json().get('ok') is False)
        check("the replay attempt didn't grant a session",
              alice6.get('/api/me').get_json().get('logged_in') is False)

        r = alice6.post('/api/webauthn/login/backup',
                         json={'code': backup_codes[1].lower().replace('-', ' ')})
        check('a differently-cased, un-dashed but otherwise correct code still works (normalized)',
              r.get_json().get('ok') is True)

        # ── regenerating invalidates the whole previous batch ────────────
        r = alice5.post('/api/webauthn/backup-codes/generate')
        new_codes = r.get_json().get('codes')
        check('regenerating returns a fresh batch of 10', isinstance(new_codes, list) and len(new_codes) == 10)

        alice7 = wc.app.test_client()
        alice7.post('/api/login', json={'username': 'alice', 'password': 'correct-horse-battery', 'mode': 'login'})
        r = alice7.post('/api/webauthn/login/backup', json={'code': backup_codes[2]})
        check('an old, never-used code from before regeneration no longer works',
              r.get_json().get('ok') is False)

        alice8 = wc.app.test_client()
        alice8.post('/api/login', json={'username': 'alice', 'password': 'correct-horse-battery', 'mode': 'login'})
        r = alice8.post('/api/webauthn/login/backup', json={'code': new_codes[0]})
        check('a code from the new batch works', r.get_json().get('ok') is True)

        # ── removing the passkey drops the 2FA requirement ───────────────
        alice2.post('/api/webauthn/credentials/remove', json={'id': cred_id})
        r = alice2.get('/api/webauthn/credentials')
        check('the credential list is empty after removal', r.get_json().get('credentials') == [])

        alice4 = wc.app.test_client()
        r = alice4.post('/api/login', json={'username': 'alice', 'password': 'correct-horse-battery', 'mode': 'login'})
        check('with no passkeys left, password alone logs in again',
              r.get_json().get('ok') is True and 'need_webauthn' not in r.get_json())

        r = alice4.post('/api/webauthn/backup-codes/generate')
        check('generating backup codes is refused with zero passkeys enrolled',
              r.status_code == 400 and r.get_json().get('ok') is False)

        print(f"\n{passed} passed")
    finally:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(b'stop', ('127.0.0.1', port))
        except Exception:
            pass
        os.chdir(prev_cwd)


if __name__ == '__main__':
    main()
