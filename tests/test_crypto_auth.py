"""
Tests for Ed25519 sender authentication (v2).

The headline case is group impersonation: in a group every member shares one
symmetric key, so the ciphertext decrypts for everyone regardless of who sent
it. Only the Ed25519 signature can tell a genuine sender from a member forging
someone else's name. These tests prove the forgery is caught.

Run:  python tests/test_crypto_auth.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.hazmat.primitives.serialization import (  # noqa: E402
    Encoding, NoEncryption, PrivateFormat,
)

from crypto_utils import (  # noqa: E402
    Identity, encrypt, decrypt, generate_group_key,
    build_signed, open_signed, split_bundle, verify_sig, KEY_LEN,
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
    print("crypto_auth")

    alice, bob = Identity(), Identity()

    # ── key bundle ──────────────────────────────────────────────────────
    bundle = alice.public_bundle()
    check('bundle is X25519(32) + Ed25519(32)', len(bundle) == 2 * KEY_LEN)
    x, ed = split_bundle(bundle)
    check('bundle splits back to the two public keys',
          x == alice.public_bytes() and ed == alice.verify_bytes())
    x32, ed_none = split_bundle(alice.public_bytes())   # legacy 32-byte key
    check('legacy 32-byte key splits with no verify key', ed_none is None)

    # ── raw sign / verify ───────────────────────────────────────────────
    sig = alice.sign(b'hello')
    check('own signature verifies', verify_sig(alice.verify_bytes(), b'hello', sig))
    check('signature fails on tampered data', not verify_sig(alice.verify_bytes(), b'hell0', sig))
    check("signature fails under bob's key", not verify_sig(bob.verify_bytes(), b'hello', sig))

    # ── signed payload framing ──────────────────────────────────────────
    ctx = b'alice\x00#room'
    blob = build_signed(alice, ctx, 'привет группе'.encode())
    pt, status = open_signed(blob, alice.verify_bytes(), ctx)
    check('genuine signed payload is verified', status == 'verified' and pt.decode() == 'привет группе')
    pt, status = open_signed(blob, None, ctx)
    check('without a verify key status is unverified', status == 'unverified')
    pt, status = open_signed(blob, alice.verify_bytes(), b'alice\x00#other')
    check('wrong context is treated as forged', status == 'forged')
    pt, status = open_signed(b'just plain bytes', alice.verify_bytes(), ctx)
    check('unsigned legacy payload is reported as unsigned', status == 'unsigned')

    # ── GROUP IMPERSONATION — the headline case ─────────────────────────
    gk = generate_group_key()             # alice, bob and the attacker share gk
    # Genuine message from alice to the group
    a_ctx = b'alice\x00#room'
    wire = encrypt(build_signed(alice, a_ctx, b'meet at 6'), gk)
    plain = decrypt(wire, gk)             # every member can decrypt
    pt, status = open_signed(plain, alice.verify_bytes(), a_ctx)
    check('genuine group message from alice verifies', status == 'verified' and pt == b'meet at 6')

    # Bob forges a message claiming to be alice, using the shared group key
    forged = encrypt(build_signed(bob, a_ctx, b'meet at 9 instead'), gk)
    plain = decrypt(forged, gk)           # decrypts fine — same group key!
    check('forged ciphertext still decrypts under the shared key', plain is not None)
    # ...but verified against ALICE's key (the claimed sender) it is rejected
    pt, status = open_signed(plain, alice.verify_bytes(), a_ctx)
    check('forgery claiming to be alice is caught', status == 'forged')

    # ── DM defence in depth ─────────────────────────────────────────────
    shared_ab = alice.derive_shared_key(bob.public_bundle())
    shared_ba = bob.derive_shared_key(alice.public_bundle())
    check('ECDH agrees over the bundle (uses only the X25519 half)', shared_ab == shared_ba)
    dm_ctx = b'alice\x00bob'
    dm = encrypt(build_signed(alice, dm_ctx, b'hi bob'), shared_ab)
    pt, status = open_signed(decrypt(dm, shared_ba), alice.verify_bytes(), dm_ctx)
    check('signed DM verifies end to end', status == 'verified' and pt == b'hi bob')

    # ── identity persistence & legacy upgrade ───────────────────────────
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 'id.key')
        ident = Identity()
        ident.save(p)
        check('saved identity is 64 bytes (both private keys)',
              os.path.getsize(p) == 2 * KEY_LEN)
        loaded = Identity.load(p)
        check('loaded identity keeps the same signing key',
              loaded.verify_bytes() == ident.verify_bytes())
        check('loaded identity keeps the same X25519 key',
              loaded.public_bytes() == ident.public_bytes())

        # Simulate an old 32-byte X25519-only file → must upgrade in place
        legacy = os.path.join(d, 'legacy.key')
        with open(legacy, 'wb') as f:
            f.write(ident.private_key.private_bytes(
                Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
        check('legacy key file starts at 32 bytes', os.path.getsize(legacy) == KEY_LEN)
        up = Identity.load(legacy)
        check('legacy key is upgraded to 64 bytes on load', os.path.getsize(legacy) == 2 * KEY_LEN)
        check('upgraded identity keeps its original X25519 key',
              up.public_bytes() == ident.public_bytes())

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
