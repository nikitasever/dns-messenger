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
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import RelayServer                                   # noqa: E402
from crypto_utils import (                                        # noqa: E402
    Identity, poll_signing_input, fpoll_signing_input,
    glist_signing_input, reg_signing_input,
)
from protocol import b32encode, b32decode, chunk_string, MAX_LABEL_LEN, gen_nonce    # noqa: E402

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


def poll_L(user, ident, nonce=None, ts=None):
    nonce = nonce or gen_nonce()
    ts = ts if ts is not None else str(int(time.time()))
    sig = ident.sign(poll_signing_input(user, nonce, ts))
    return [user, nonce, ts] + chunk_string(b32encode(sig), MAX_LABEL_LEN)


def fpoll_L(user, ident, nonce=None, ts=None):
    nonce = nonce or gen_nonce()
    ts = ts if ts is not None else str(int(time.time()))
    sig = ident.sign(fpoll_signing_input(user, nonce, ts))
    return [user, nonce, ts] + chunk_string(b32encode(sig), MAX_LABEL_LEN)


def glist_L(user, ident, nonce=None, ts=None):
    nonce = nonce or gen_nonce()
    ts = ts if ts is not None else str(int(time.time()))
    sig = ident.sign(glist_signing_input(user, nonce, ts))
    return [user, nonce, ts] + chunk_string(b32encode(sig), MAX_LABEL_LEN)


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

    # ── stale timestamp is refused even with a never-before-seen nonce ──
    # This is the guarantee seen_poll_nonces alone can't give: it only lives
    # in memory, so a relay restart forgets every nonce it had seen, and a
    # captured (nonce, sig) pair from before the restart would otherwise
    # replay cleanly against the fresh in-memory state. A signed, bounded
    # timestamp closes that gap independently of what the relay remembers.
    stale_ts = str(int(time.time()) - 999)
    stale_labels = poll_L('alice', alice, ts=stale_ts)
    check('a stale (out-of-window) timestamp is refused even with a fresh nonce',
          srv._h_poll(stale_labels) == 'ERR:auth')
    future_ts = str(int(time.time()) + 999)
    future_labels = poll_L('alice', alice, ts=future_ts)
    check('a far-future timestamp is refused too (clock-skew abuse)',
          srv._h_poll(future_labels) == 'ERR:auth')

    # ── file-inbox poll: same protection, distinct signing context ──────
    srv.files['fid1'] = {'from': 'bob', 'name': 'doc', 'size': '10',
                         'complete': True, 'to': 'alice'}
    srv.file_inbox['alice'] = ['fid1']
    check('an unsigned file-poll on a pinned inbox is refused',
          srv._h_fpoll(['alice']) == 'ERR:auth')
    check('the file is still queued after the refused poll',
          srv.file_inbox['alice'] == ['fid1'])
    check('a file-poll signed by the wrong key is refused',
          srv._h_fpoll(fpoll_L('alice', mallory)) == 'ERR:auth')
    # a DM-poll signature must NOT work as a file-poll (distinct context)
    check('a DM-poll signature cannot be replayed as a file-poll',
          srv._h_fpoll(poll_L('alice', alice)) == 'ERR:auth')
    check('the file survives all refused polls', srv.file_inbox['alice'] == ['fid1'])
    r = srv._h_fpoll(fpoll_L('alice', alice))
    check('a valid signed file-poll delivers the file', r == 'FILE:fid1:bob:doc:10')

    # ── group-list: a pinned user's memberships can't be enumerated ──────
    srv.groups['grp1'] = {'creator': 'alice', 'members': {'alice'},
                          'keys': {'alice': {'data': 'k', 'from_user': 'alice'}}}
    check('an unsigned group-list on a pinned name is refused',
          srv._h_glist(['alice']) == 'ERR:auth')
    check('a group-list signed by the wrong key is refused',
          srv._h_glist(glist_L('alice', mallory)) == 'ERR:auth')
    check('a DM-poll signature cannot be replayed as a group-list',
          srv._h_glist(poll_L('alice', alice)) == 'ERR:auth')
    check('a valid signed group-list returns the memberships',
          srv._h_glist(glist_L('alice', alice)).startswith('GROUPS:grp1:'))

    # ── legacy backward-compat ──────────────────────────────────────────
    carol = Identity()
    check('an unsigned (legacy) register succeeds', srv._h_register(reg_L('carol', carol, signed=False)).startswith('OK'))
    check('a legacy name is NOT pinned', srv.users['carol']['pinned'] is False)
    srv.mailbox['carol'].append({'from': 'x', 'data': 'ct'})
    check('a legacy name still polls unsigned', srv._h_poll(['carol', '0']) == 'MSG:x:ct')
    srv.files['fid2'] = {'from': 'z', 'name': 'f', 'size': '5', 'complete': True, 'to': 'carol'}
    srv.file_inbox['carol'] = ['fid2']
    check('a legacy name still file-polls unsigned', srv._h_fpoll(['carol']) == 'FILE:fid2:z:f:5')
    srv.groups['grp2'] = {'creator': 'carol', 'members': {'carol'},
                          'keys': {'carol': {'data': 'k', 'from_user': 'carol'}}}
    check('a legacy name still lists groups unsigned',
          srv._h_glist(['carol']).startswith('GROUPS:grp2:'))

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

    # ── A3: getkey exposes the pinned flag so a truncated (32-byte) bundle
    # served for a PINNED (should always be 64-byte) identity is detectable
    # as an inconsistent, tampered response rather than silently accepted
    # as "just a legacy peer" (which would downgrade Ed25519 verification
    # to unverified forever) ────────────────────────────────────────────
    res = srv._h_getkey(['alice'])
    check("getkey reports pinned=1 for alice's fully-signed bundle",
          res.startswith('KEY:1:'))
    check("getkey's bundle for a pinned user is the full 64-byte bundle",
          len(b32decode(res.split(':', 2)[2])) == 64)
    res_legacy = srv._h_getkey(['carol'])
    check('getkey reports pinned=1 for carol too (upgraded to pinned above)',
          res_legacy.startswith('KEY:1:'))

    import os as _os, tempfile as _tempfile
    _prev = _os.getcwd()
    _os.chdir(_tempfile.mkdtemp())
    try:
        import web_client
        eve = web_client.UserMessenger('eve', None, persist_identity=False)

        class _FakeTransport:
            """Simulates a relay that reports pinned=1 but truncates the bundle."""
            def query(self, labels):
                return 'KEY:1:' + b32encode(alice.public_bytes())   # only 32 bytes

        eve.transport = _FakeTransport()
        check('a pinned=1 response truncated to 32 bytes is rejected, not pinned',
              eve.get_peer_key('alice') is None and 'alice' not in eve.peer_keys)
    finally:
        _os.chdir(_prev)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
