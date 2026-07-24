"""
Relay-layer request authentication: registration pinning (TOFR) + signed poll.

The relay is stateless DNS, so it can't tell who is asking from the transport.
These tests drive the RelayServer handlers directly with real Ed25519-signed
payloads and verify:

  - a signed registration PINS a name to its key;
  - a pinned name rejects re-registration / polling by any other key;
  - a valid signed poll delivers, an unsigned poll on a pinned name is refused,
    and a replayed signed poll (same nonce) is refused;
  - legacy unsigned clients still register (unpinned) and poll unsigned;
  - the real owner (same persisted key) upgrades a legacy name to pinned, but an
    attacker with a different key cannot pin someone else's legacy name.

Run:  python tests/test_relay_auth.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import RelayServer                                   # noqa: E402
from crypto_utils import Identity, poll_signing_input, reg_signing_input  # noqa: E402
from protocol import b32encode, chunk_string, MAX_LABEL_LEN, gen_nonce    # noqa: E402

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"  [FAIL] {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  [ok] {name}")


def reg_L(user, ident, signed=True):
    """Labels for _h_register (without the command label)."""
    bundle = ident.public_bundle()
    payload = b32encode(bundle)
    if signed:
        payload += b32encode(ident.sign(reg_signing_input(user, bundle)))
    return [user] + chunk_string(payload, MAX_LABEL_LEN)


def poll_L(user, ident, nonce=None):
    nonce = nonce or gen_nonce()
    sig = ident.sign(poll_signing_input(user, nonce))
    return [user, nonce] + chunk_string(b32encode(sig), MAX_LABEL_LEN)


def main():
    print("relay auth")
    srv = RelayServer('msg.tunnel.local')

    alice = Identity()
    mallory = Identity()

    # ── registration pinning ────────────────────────────────────────────
    check('signed register succeeds', srv._h_register(reg_L('alice', alice)).startswith('OK'))
    check('the name is now pinned', srv.users['alice']['pinned'] is True)

    check('a different key cannot re-register a pinned name',
          srv._h_register(reg_L('alice', mallory)) == 'ERR:pinned')
    check('the pinned bundle is unchanged after the attempt',
          srv.users['alice']['bundle'] == alice.public_bundle())
    check('the original owner can re-register (idempotent)',
          srv._h_register(reg_L('alice', alice)).startswith('OK'))

    # ── signed poll ─────────────────────────────────────────────────────
    srv.mailbox['alice'].append({'from': 'bob', 'data': 'ciphertext1'})
    check('an unsigned poll on a pinned mailbox is refused',
          srv._h_poll(['alice', '0']) == 'ERR:auth')
    check('the message is still queued after the refused poll',
          len(srv.mailbox['alice']) == 1)
    check('a poll signed by the wrong key is refused',
          srv._h_poll(poll_L('alice', mallory)) == 'ERR:auth')

    r = srv._h_poll(poll_L('alice', alice))
    check('a valid signed poll delivers the message', r == 'MSG:bob:ciphertext1')

    # ── replay protection ───────────────────────────────────────────────
    srv.mailbox['alice'].append({'from': 'bob', 'data': 'ciphertext2'})
    nonce = gen_nonce()
    labels = poll_L('alice', alice, nonce=nonce)
    check('first use of a signed nonce delivers', srv._h_poll(labels) == 'MSG:bob:ciphertext2')
    srv.mailbox['alice'].append({'from': 'bob', 'data': 'ciphertext3'})
    check('replaying the same signed nonce is refused', srv._h_poll(labels) == 'ERR:replay')
    check('the message survives the replayed poll', len(srv.mailbox['alice']) == 1)

    # ── legacy backward-compat ──────────────────────────────────────────
    carol = Identity()
    check('an unsigned (legacy) register succeeds', srv._h_register(reg_L('carol', carol, signed=False)).startswith('OK'))
    check('a legacy name is NOT pinned', srv.users['carol']['pinned'] is False)
    srv.mailbox['carol'].append({'from': 'x', 'data': 'ct'})
    check('a legacy name still polls unsigned', srv._h_poll(['carol', '0']) == 'MSG:x:ct')

    # same owner (persisted key) upgrades the legacy name to pinned
    check('the real owner upgrades a legacy name to pinned',
          srv._h_register(reg_L('carol', carol, signed=True)).startswith('OK')
          and srv.users['carol']['pinned'] is True)

    # attacker with a different key cannot pin someone else's legacy name
    dave = Identity()
    attacker = Identity()
    srv._h_register(reg_L('dave', dave, signed=False))         # legacy, unpinned
    srv._h_register(reg_L('dave', attacker, signed=True))      # different key, signed
    check('an attacker cannot pin a legacy name they do not own',
          srv.users['dave']['pinned'] is False)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
