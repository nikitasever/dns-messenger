"""
Prekey bootstrap / replenish / rotation (web_client.bootstrap_or_replenish_prekeys).

Covers the gap found right after Phase 1 first shipped: the signed prekey was
generated once and never rotated. A signed prekey that lives forever means a
leaked one gives an attacker an indefinite MITM window on new conversations;
periodic rotation closes that.

Runs in an isolated temp directory (prekeys.key touches disk).

Run:  python tests/test_prekey_rotation.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: E402

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"  [FAIL] {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  [ok] {name}")


def main():
    print("prekey rotation")

    prev = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:
        import web_client as wc
        from crypto_utils import Identity, verify_sig

        identity = Identity()

        # ── bootstrap from nothing ───────────────────────────────────────
        store, changed = wc.bootstrap_or_replenish_prekeys(identity, None, now=1000.0)
        check('a fresh bootstrap is reported as changed', changed)
        check('a full one-time pool is generated',
              len(store['one_time']) == wc.ONE_TIME_PREKEY_POOL_TARGET)
        original_signed_pub = store['signed_pub']

        # ── calling again shortly after: nothing to do ──────────────────
        store, changed = wc.bootstrap_or_replenish_prekeys(identity, store, now=1000.0 + 60)
        check('re-checking soon after (pool full, prekey fresh) reports no change', not changed)
        check('the signed prekey is untouched', store['signed_pub'] == original_signed_pub)

        # ── consume most of the one-time pool: replenish triggers ───────
        consumed = list(store['one_time'].keys())[:wc.ONE_TIME_PREKEY_POOL_TARGET - 5]
        for pub in consumed:
            del store['one_time'][pub]
        check('pool is now below the replenish threshold',
              len(store['one_time']) < wc.ONE_TIME_PREKEY_REPLENISH_THRESHOLD)
        store, changed = wc.bootstrap_or_replenish_prekeys(identity, store, now=1000.0 + 120)
        check('a depleted pool triggers a replenish', changed)
        check('the pool is topped back up to the target size',
              len(store['one_time']) == wc.ONE_TIME_PREKEY_POOL_TARGET)
        check("the signed prekey wasn't touched by a mere replenish",
              store['signed_pub'] == original_signed_pub)

        # ── far in the future: signed prekey must rotate ────────────────
        far_future = 1000.0 + wc.SIGNED_PREKEY_ROTATE_AFTER + 3600
        store, changed = wc.bootstrap_or_replenish_prekeys(identity, store, now=far_future)
        check('an aged-out signed prekey triggers rotation', changed)
        check('the rotated signed prekey differs from the original',
              store['signed_pub'] != original_signed_pub)
        check("the new signed prekey's signature verifies under the same identity",
              verify_sig(identity.verify_bytes(), store['signed_pub'], store['signed_sig']))
        check('signed_ts was updated to the rotation time', store['signed_ts'] == far_future)

        # ── the returned private key object actually matches the public one ─
        check("store['signed_priv'] is the actual private half of signed_pub",
              store['signed_priv'].public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
              == store['signed_pub'])

        print(f"\n{passed} passed")
    finally:
        os.chdir(prev)


if __name__ == '__main__':
    main()
