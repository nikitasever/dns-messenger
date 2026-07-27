"""
Account-recovery code (forgot-password path).

The account password doubles as the encryption key for identity.key (see
test_identity_enc.py), so a server-side "reset password" is impossible by
construction — the server never holds anything that decrypts the identity
without it. Recovery works around this the only way that's actually sound:
a second, independent wrap of the same raw identity bytes, encrypted under
a high-entropy code shown to the user exactly once (generate_recovery_code),
which can later be used to re-derive the identity and re-wrap it under a new
password (consume_recovery_code) without ever touching the server's own
secrets.

Runs in an isolated temp directory so it never touches the repo's real
.messenger_<user>/ directories.

Run:  python tests/test_recovery.py
"""
import os
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
    print("account recovery")

    prev = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:
        import web_client as wc
        from crypto_utils import Identity

        username = 'alice'
        os.makedirs(f'.messenger_{username}', exist_ok=True)
        identity = Identity()
        raw_priv = identity.private_bytes()

        # ── no code yet ──────────────────────────────────────────────────
        check('has_recovery_code is False before any code is generated',
              not wc.has_recovery_code(username))
        check('consume_recovery_code with no file on disk returns None',
              wc.consume_recovery_code(username, 'ANYTHING') is None)

        # ── generate ─────────────────────────────────────────────────────
        code = wc.generate_recovery_code(username, identity)
        check('has_recovery_code is True once generated', wc.has_recovery_code(username))
        check('the generated code is formatted in 4-char groups',
              all(len(g) == 4 for g in code.split('-')))

        on_disk = open(wc._recovery_file(username), 'rb').read()
        check('the raw private key never appears in the recovery file on disk',
              raw_priv not in on_disk)

        # ── consume: right code recovers the exact same keys ────────────
        recovered = wc.consume_recovery_code(username, code)
        check('the right code recovers an Identity', recovered is not None)
        check('the recovered identity has the exact same private key material',
              recovered.private_bytes() == raw_priv)

        # ── consume: normalization tolerates dashes/case/whitespace ──────
        messy = ' ' + code.lower().replace('-', ' ') + ' '
        check('a lowercased, differently-separated code still works',
              wc.consume_recovery_code(username, messy) is not None)

        # ── consume: wrong code is rejected ──────────────────────────────
        check('a wrong code returns None', wc.consume_recovery_code(username, 'X' * 24) is None)
        check('an empty code returns None', wc.consume_recovery_code(username, '') is None)

        # ── regenerating invalidates the old code ────────────────────────
        new_code = wc.generate_recovery_code(username, identity)
        check('a freshly regenerated code differs from the old one', new_code != code)
        check('the OLD code no longer decrypts anything after regeneration',
              wc.consume_recovery_code(username, code) is None)
        check('the NEW code decrypts to the same identity',
              wc.consume_recovery_code(username, new_code).private_bytes() == raw_priv)

        # ── /api/recovery/reset end-to-end ───────────────────────────────
        wc.app.config['TESTING'] = True
        h, s = wc._hash_password('old-password-123')
        wc.save_account(username, h, s)
        client = wc.app.test_client()

        bad = client.post('/api/recovery/reset', json={
            'username': username, 'code': 'WRONGWRONGWRONGWRONGWR', 'new_password': 'new-password-456',
        }).get_json()
        check('reset with a wrong code fails', not bad['ok'])
        check('accounts.json password hash is unchanged after a failed reset',
              wc._verify_password('old-password-123', *[
                  wc.get_accounts()[username][k] for k in ('hash', 'salt')]))

        good = client.post('/api/recovery/reset', json={
            'username': username, 'code': new_code, 'new_password': 'new-password-456',
        }).get_json()
        check('reset with the right code succeeds', good['ok'])
        check('the response ships a freshly-issued replacement code', good['code'] != new_code)

        accounts = wc.get_accounts()
        check('the account now verifies under the NEW password',
              wc._verify_password('new-password-456', accounts[username]['hash'], accounts[username]['salt']))
        check('the OLD password no longer verifies',
              not wc._verify_password('old-password-123', accounts[username]['hash'], accounts[username]['salt']))

        reloaded = Identity.load(f'.messenger_{username}/identity.key', password='new-password-456')
        check('identity.key on disk now decrypts under the new password to the same keys',
              reloaded.private_bytes() == raw_priv)

        check('the code used for a successful reset is itself now spent',
              wc.consume_recovery_code(username, new_code) is None)

        print(f"\n{passed} passed")
    finally:
        os.chdir(prev)


if __name__ == '__main__':
    main()
