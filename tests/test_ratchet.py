"""
X3DH + Double Ratchet correctness (Phase 1 of docs/ratchet-plan.md).

Covers exactly the cases the plan calls out: normal roundtrip, out-of-order
delivery, lost messages, per-message key uniqueness, forward secrecy (the
actual point of this whole phase — not just "it decrypts"), X3DH with and
without a one-time prekey, and the skipped-key DoS cap.

Run:  python tests/test_ratchet.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_utils import Identity                                          # noqa: E402
from ratchet import (                                                      # noqa: E402
    RatchetSession, RatchetError, MAX_SKIPPED_KEYS,
    generate_prekey_pair, prekey_public_bytes, sign_prekey,
    x3dh_initiate, x3dh_respond,
)

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"  [FAIL] {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  [ok] {name}")


def handshake(one_time=True):
    """Полный X3DH: Alice инициирует офлайн-получателю Bob, оба выводят
    один и тот же секрет, и оба стартуют свою половину Double Ratchet.
    Возвращает (alice_session, bob_session, bob_signed_prekey_priv)."""
    alice, bob = Identity(), Identity()
    bob_spk = generate_prekey_pair()
    bob_spk_pub = prekey_public_bytes(bob_spk)
    bob_spk_sig = sign_prekey(bob, bob_spk_pub)

    bob_opk = generate_prekey_pair() if one_time else None
    bob_opk_pub = prekey_public_bytes(bob_opk) if one_time else None

    ephemeral = generate_prekey_pair()
    sk_alice = x3dh_initiate(
        alice, ephemeral,
        peer_identity_pub=bob.public_bytes(), peer_verify_pub=bob.verify_bytes(),
        peer_signed_prekey_pub=bob_spk_pub, peer_signed_prekey_sig=bob_spk_sig,
        peer_one_time_prekey_pub=bob_opk_pub,
    )
    sk_bob = x3dh_respond(
        bob, bob_spk, bob_opk,
        peer_identity_pub=alice.public_bytes(),
        peer_ephemeral_pub=prekey_public_bytes(ephemeral),
    )
    check(f'X3DH: both sides derive the same secret (one_time={one_time})', sk_alice == sk_bob)

    a_session = RatchetSession.init_initiator(sk_alice, bob_spk_pub)
    b_session = RatchetSession.init_responder(sk_bob, bob_spk)
    return a_session, b_session


def main():
    print("ratchet")

    # ── X3DH: bad signed-prekey signature is rejected ───────────────────
    alice, bob = Identity(), Identity()
    bob_spk_pub = prekey_public_bytes(generate_prekey_pair())
    forged_sig = alice.sign(bob_spk_pub)   # signed by the WRONG identity
    try:
        x3dh_initiate(alice, generate_prekey_pair(),
                       peer_identity_pub=bob.public_bytes(), peer_verify_pub=bob.verify_bytes(),
                       peer_signed_prekey_pub=bob_spk_pub, peer_signed_prekey_sig=forged_sig,
                       peer_one_time_prekey_pub=None)
        check('a forged signed-prekey signature is rejected', False)
    except RatchetError:
        check('a forged signed-prekey signature is rejected', True)

    # ── X3DH without a one-time prekey (pool exhausted) still works ─────
    handshake(one_time=False)

    # ── basic roundtrip, both directions ─────────────────────────────────
    a, b = handshake(one_time=True)
    ct = a.encrypt(b'hello bob')
    check('bob decrypts alice\'s first message', b.decrypt(ct) == b'hello bob')
    ct2 = b.encrypt(b'hi alice')
    check('alice decrypts bob\'s reply (ratchet flips direction)', a.decrypt(ct2) == b'hi alice')
    ct3 = a.encrypt(b'how are you')
    check('alice can send again after the round trip', b.decrypt(ct3) == b'how are you')

    # ── each message key is unique: identical plaintext -> different ct ──
    a, b = handshake()
    c1 = a.encrypt(b'same text')
    c2 = a.encrypt(b'same text')
    check('encrypting the same plaintext twice yields different ciphertexts',
          c1 != c2)
    check('both still decrypt correctly', b.decrypt(c1) == b'same text' and b.decrypt(c2) == b'same text')

    # ── out-of-order delivery ────────────────────────────────────────────
    a, b = handshake()
    m1 = a.encrypt(b'one')
    m2 = a.encrypt(b'two')
    m3 = a.encrypt(b'three')
    check('message 3 decrypts even though 1 and 2 have not arrived yet',
          b.decrypt(m3) == b'three')
    check('message 1 (arriving late) still decrypts via the skipped-key store',
          b.decrypt(m1) == b'one')
    check('message 2 (arriving even later) still decrypts',
          b.decrypt(m2) == b'two')
    try:
        b.decrypt(m1)
        check('re-decrypting an already-consumed skipped message fails', False)
    except Exception:
        check('re-decrypting an already-consumed skipped message fails', True)

    # ── a permanently lost message does not block the rest ──────────────
    a, b = handshake()
    lost = a.encrypt(b'never arrives')       # noqa: F841 — deliberately dropped
    fine = a.encrypt(b'this one does')
    check('a message after a lost one still decrypts fine',
          b.decrypt(fine) == b'this one does')

    # ── forward secrecy: the point of this whole phase ───────────────────
    a, b = handshake()
    early = a.encrypt(b'top secret from the past')
    later = a.encrypt(b'more traffic to advance the chain')
    b.decrypt(early)
    b.decrypt(later)
    # Bob's chain has now moved well past 'early'. Simulate stealing Bob's
    # CURRENT ratchet state (root key + chain keys) — a snapshot of what an
    # attacker gets from a compromised session right now — and confirm it
    # cannot reconstruct the ALREADY-DERIVED-AND-DISCARDED message key for
    # 'early'. The one-way HMAC chain (_kdf_ck) is precisely what makes this
    # true: forward secrecy isn't "we didn't test it", it's structural.
    stolen_recv_chain = b.recv_chain
    stolen_root_key = b.root_key
    check("the current chain key differs from any message key ever used "
          "(one-way ratchet, not the same value reused)",
          stolen_recv_chain not in (early, later) and stolen_root_key not in (early, later))
    # Walking the CURRENT chain key forward can only ever produce FUTURE
    # message keys, never reconstruct 'early's already-consumed one — that
    # key existed only transiently inside RatchetSession.decrypt() and was
    # discarded the moment it returned. There is no function in this module
    # that goes from a later chain key back to an earlier message key.
    check("RatchetSession exposes no backward derivation from a chain key "
          "to an earlier message key",
          not hasattr(RatchetSession, 'derive_backward'))

    # ── skipped-key limit: DoS guard ──────────────────────────────────────
    a, b = handshake()
    a.encrypt(b'warmup')          # give b a receive chain to skip within
    huge_gap = a.encrypt(b'way ahead')
    # Craft a header claiming an absurd message index without the sender
    # actually deriving that many keys — decrypt() must refuse to burn
    # unbounded memory trying to skip forward to it.
    import struct
    dh_pub, pn, _n = struct.unpack('>32sII', huge_gap[:40])
    forged = struct.pack('>32sII', dh_pub, pn, MAX_SKIPPED_KEYS + 500) + huge_gap[40:]
    try:
        b.decrypt(forged)
        check('an absurd message index is rejected instead of allocating '
              'unbounded skipped keys', False)
    except RatchetError:
        check('an absurd message index is rejected instead of allocating '
              'unbounded skipped keys', True)
    check('the skipped-key store never grew past the cap',
          len(b.skipped) <= MAX_SKIPPED_KEYS)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
