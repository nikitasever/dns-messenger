"""
At-rest encryption of the identity key file (scan #2, full fix).

A registered user's identity.key (raw X25519 + Ed25519 private keys) is encrypted
with a key derived from the account password (scrypt + ChaCha20-Poly1305). Anyone
who reads the file — backup leak, shared host, malware — gets only ciphertext
without the password. Anonymous users have no password, so their file stays raw
(chmod-only), same as before.

Run:  python tests/test_identity_enc.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_utils import (                                    # noqa: E402
    Identity, IdentityLocked, IDENTITY_MAGIC, verify_sig,
)

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"  [FAIL] {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  [ok] {name}")


def main():
    print("identity encryption")
    d = tempfile.mkdtemp()
    path = os.path.join(d, 'identity.key')

    ident = Identity()
    raw_priv = ident.private_bytes()
    bundle = ident.public_bundle()

    # ── encrypted save ──────────────────────────────────────────────────
    ident.save(path, password='correct horse battery')
    on_disk = open(path, 'rb').read()
    check('the encrypted file carries the magic header', on_disk.startswith(IDENTITY_MAGIC))
    check('the raw private key never appears in the file on disk', raw_priv not in on_disk)

    # ── load requires the right password ────────────────────────────────
    try:
        Identity.load(path)
        check('load without a password raises IdentityLocked', False)
    except IdentityLocked:
        check('load without a password raises IdentityLocked', True)

    try:
        Identity.load(path, password='wrong password')
        check('load with the wrong password raises IdentityLocked', False)
    except IdentityLocked:
        check('load with the wrong password raises IdentityLocked', True)

    back = Identity.load(path, password='correct horse battery')
    check('the right password recovers the exact same keys',
          back.private_bytes() == raw_priv and back.public_bundle() == bundle)
    # the recovered signing key really works
    sig = back.sign(b'hello')
    check('the recovered signing key still produces valid signatures',
          verify_sig(back.verify_bytes(), b'hello', sig))

    # ── anonymous / legacy: no password -> raw file, still readable ──────
    raw_path = os.path.join(d, 'anon.key')
    anon = Identity()
    anon.save(raw_path)                       # no password
    disk = open(raw_path, 'rb').read()
    check('a password-less save writes a raw (unencrypted) file',
          not disk.startswith(IDENTITY_MAGIC) and disk == anon.private_bytes())
    reloaded = Identity.load(raw_path)        # no password needed
    check('a raw file still loads without a password',
          reloaded.private_bytes() == anon.private_bytes())

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
