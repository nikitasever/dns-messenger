"""
Relay memory bounds (proactive, beyond the external scans).

The relay's payload stores are filled by UNauthenticated senders — anyone can
send a message or a file header. Without bounds, a flood of 512 KB file headers
or never-completed chunk assemblies OOMs the relay. These tests prove the inline
caps (hard bound at insert) and the TTL sweep (_evict) keep every store bounded.

Run:  python tests/test_relay_dos.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server                                                   # noqa: E402
from server import RelayServer                                  # noqa: E402
from protocol import (                                          # noqa: E402
    CMD_SEND, CMD_FILE_HEADER, b32encode,
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
    print("relay dos bounds")
    srv = RelayServer('msg.tunnel.local')

    # ── file-header cap ─────────────────────────────────────────────────
    for i in range(server.MAX_FILES + 60):
        srv._h_fheader([f'victim', 'attacker', f'fid{i}', 'nn', '100', '1'])
    check('the file store never exceeds MAX_FILES',
          len(srv.files) <= server.MAX_FILES)

    # ── incomplete-assembly cap ─────────────────────────────────────────
    # total=2 but only seq 0 sent → each mid stays incomplete forever.
    payload = b32encode(b'x')
    for i in range(server.MAX_INCOMPLETE + 60):
        srv._h_send(['victim', 'attacker', f'mid{i}', '0', '2', payload])
    check('incomplete message assemblies are capped',
          len(srv.msg_chunks) <= server.MAX_INCOMPLETE)

    # ── mailbox length cap ──────────────────────────────────────────────
    # total=1 single-chunk → completes immediately → lands in the mailbox.
    for i in range(server.MAX_MAILBOX_MSGS + 60):
        srv._h_send(['floodee', 'attacker', f'm{i}', '0', '1', b32encode(b'hi')])
    check('a single mailbox is capped to MAX_MAILBOX_MSGS',
          len(srv.mailbox['floodee']) <= server.MAX_MAILBOX_MSGS)
    check('the mailbox kept the most recent messages (dropped oldest)',
          srv.mailbox['floodee'][-1]['id'] == f'm{server.MAX_MAILBOX_MSGS + 59}')

    # ── TTL sweep removes stale files even without new inserts ──────────
    srv2 = RelayServer('msg.tunnel.local')
    srv2._h_fheader(['u', 'a', 'freshfid', 'nn', '10', '1'])
    srv2._h_fheader(['u', 'a', 'stalefid', 'nn', '10', '1'])
    srv2.files['stalefid']['ts'] -= (server.FILE_TTL + 100)   # make it old
    srv2._last_evict = 0                                       # force a sweep
    srv2._evict()
    check('the TTL sweep drops a stale file', 'stalefid' not in srv2.files)
    check('the TTL sweep keeps a fresh file', 'freshfid' in srv2.files)

    # ── TTL sweep removes stale incomplete assemblies ───────────────────
    srv2._h_send(['u', 'a', 'stalemid', '0', '2', payload])   # incomplete
    srv2.msg_meta['stalemid'] = srv2.msg_meta['stalemid'][:3] + (
        srv2.msg_meta['stalemid'][3] - (server.ASSEMBLY_TTL + 100),)
    srv2._last_evict = 0
    srv2._evict()
    check('the TTL sweep drops a stale incomplete assembly',
          'stalemid' not in srv2.msg_chunks and 'stalemid' not in srv2.msg_meta)

    # ── per-ENTRY size caps (not just entry count) ──────────────────────
    check('file header with oversized total is rejected',
          srv._h_fheader(['u', 'a', 'bigfid', 'nn', '1', str(server.MAX_FILE_CHUNKS + 1)]) == 'ERR:bad_total')
    srv._h_fheader(['u', 'a', 'okfid', 'nn', '10', '2'])       # total=2
    check('a file chunk with seq >= total is rejected',
          srv._h_fchunk(['okfid', '5', 'data']) == 'ERR:bad_seq')
    check('a message with oversized total is rejected',
          srv._h_send(['b', 'a', 'mm', '0', str(server.MAX_MSG_CHUNKS + 1), b32encode(b'x')]) == 'ERR:bad_chunk')
    check('a message chunk with seq >= total is rejected',
          srv._h_send(['b', 'a', 'mm2', '5', '2', b32encode(b'x')]) == 'ERR:bad_chunk')

    # ── reassembly source binding + per-sender idempotency ──────────────
    srv._h_send(['bob', 'alice', 'shared', '0', '2', b32encode(b'aa')])
    check('a chunk for the same mid from a different sender is rejected',
          srv._h_send(['bob', 'mallory', 'shared', '1', '2', b32encode(b'bb')]) == 'ERR:mid_conflict')
    srv._h_send(['carol', 'mallory', 'dup', '0', '1', b32encode(b'x')])   # mallory completes 'dup'
    check("a real sender's message reusing another sender's mid still delivers",
          srv._h_send(['carol', 'alice', 'dup', '0', '1', b32encode(b'yy')]) == 'OK:delivered')

    # ── groups / users stores are bounded ───────────────────────────────
    from crypto_utils import Identity                                 # noqa: E402
    from protocol import chunk_string as _cs, MAX_LABEL_LEN as _ml    # noqa: E402
    server.MAX_GROUPS = 10
    for i in range(server.MAX_GROUPS + 20):
        srv._h_gcreate([f'grp{i}', 'att'])
    check('the groups store is bounded under a creation flood',
          len(srv.groups) <= server.MAX_GROUPS)
    server.MAX_USERS = 10
    for i in range(server.MAX_USERS + 20):
        srv._h_register([f'usr{i}'] + _cs(b32encode(Identity().public_bundle()), _ml))
    check('the users store is bounded under a registration flood',
          len(srv.users) <= server.MAX_USERS)

    # ── DNS/UDP amplification: `u` (list-users) reply is capped ─────────
    # Unauthenticated, response grows with total registered users, not with
    # anything in the request — the biggest single contributor to reflection
    # amplification (measured ~514x at 2000 users before this cap).
    srv2 = RelayServer('msg.tunnel.local')
    for i in range(server.MAX_LIST_USERS_REPLY + 500):
        srv2.users[f'u{i:06d}'] = {'bundle': b'x' * 64, 'pinned': False, 'ts': 0}
    res = srv2._h_list_users([])
    returned = res[len('USERS:'):].split('|')
    check('list-users reply is capped regardless of how many are registered',
          len(returned) == server.MAX_LIST_USERS_REPLY)

    # ── DNS/UDP amplification: response-rate-limiting per claimed source IP ─
    # UDP source IPs are trivially spoofable; RRL caps how much reply volume
    # the relay is willing to aim at any ONE claimed address (the classic
    # DNS-resolver mitigation for reflection abuse), not "the attacker" (whose
    # real IP never appears in a spoofed packet).
    srv3 = RelayServer('msg.tunnel.local')
    allowed = [srv3._rrl_allow('1.2.3.4') for _ in range(server.UDP_RRL_MAX + 10)]
    check('RRL allows exactly UDP_RRL_MAX replies to one claimed source per window',
          allowed.count(True) == server.UDP_RRL_MAX)
    check('RRL blocks the rest within the same window',
          allowed[server.UDP_RRL_MAX:] == [False] * 10)
    check('a different claimed source is unaffected by another one being throttled',
          srv3._rrl_allow('5.6.7.8') is True)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
