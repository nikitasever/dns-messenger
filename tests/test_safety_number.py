"""
Safety number (Phase 3 of docs/ratchet-plan.md) — identity fingerprint /
combined safety number in crypto_utils.py, and the on-disk verification
mark in web_client.py (mark_peer_verified/is_peer_verified/clear_peer_verified).

Unit-level, no Flask test client and no relay: exercises the pure crypto
primitives directly, then the storage functions in an isolated temp dir
(mirrors test_ratchet_persistence.py's shape).

Run:  python tests/test_safety_number.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crypto_utils import Identity, safety_number, format_safety_number  # noqa: E402

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"  [FAIL] {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  [ok] {name}")


def main():
    print("safety number")

    alice = Identity()
    bob = Identity()
    carol = Identity()
    ba, bb, bc = alice.public_bundle(), bob.public_bundle(), carol.public_bundle()

    n_ab = safety_number('alice', ba, 'bob', bb)
    n_ba = safety_number('bob', bb, 'alice', ba)
    check('symmetric regardless of argument order', n_ab == n_ba)
    check('is 60 decimal digits', len(n_ab) == 60 and n_ab.isdigit())

    n_ac = safety_number('alice', ba, 'carol', bc)
    check('differs for a different peer', n_ab != n_ac)

    n_ab_again = safety_number('alice', ba, 'bob', bb)
    check('deterministic for the same inputs', n_ab == n_ab_again)

    # Same key material under different usernames must NOT collide — the
    # username is folded into the fingerprint precisely so a reused key pair
    # (should one ever leak/collide) doesn't produce a matching number.
    n_swapped_names = safety_number('mallory', ba, 'bob', bb)
    check("changing a party's username changes the number",
          n_ab != n_swapped_names)

    formatted = format_safety_number(n_ab)
    groups = formatted.split(' ')
    check('formatted as 12 groups of 5 digits', len(groups) == 12 and all(len(g) == 5 for g in groups))
    check('formatting is just grouping, no digits lost', formatted.replace(' ', '') == n_ab)

    # ── on-disk verification mark ────────────────────────────────────────
    prev = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:
        import web_client as wc

        peer_bundle = bb  # "bob's pinned bundle" from alice's point of view
        check('not verified before any mark', not wc.is_peer_verified('alice', 'bob', peer_bundle))

        wc.mark_peer_verified('alice', 'bob', peer_bundle)
        check('verified after marking', wc.is_peer_verified('alice', 'bob', peer_bundle))

        # A pin change (key rotation, or a real MITM) must silently drop the
        # mark rather than keep vouching for a bundle nobody actually checked.
        check("a changed pinned bundle is reported as unverified",
              not wc.is_peer_verified('alice', 'bob', bc))

        wc.clear_peer_verified('alice', 'bob')
        check('unverified after explicit clear', not wc.is_peer_verified('alice', 'bob', peer_bundle))

        # Per-username, per-account isolation.
        wc.mark_peer_verified('alice', 'bob', peer_bundle)
        check("marking under a different local account doesn't cross-contaminate",
              not wc.is_peer_verified('carol', 'bob', peer_bundle))

        print(f"\n{passed} passed")
    finally:
        os.chdir(prev)


if __name__ == '__main__':
    main()
