"""
Tests for narrow ACK: chunk retry on packet loss, with server-side idempotency.

A message send is retried when the response is lost. The danger is duplication:
if the ACK for the *final* chunk of a single-chunk message is lost, the retry
re-delivers it — so without server-side dedup the recipient would see it twice.
These tests drive the real send path through a transport that drops the first
response to every send, proving each message is delivered exactly once.

Run:  python tests/test_reliability.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dnslib import DNSRecord, QTYPE  # noqa: E402

import protocol  # noqa: E402
from transport import _build_query  # noqa: E402
from server import RelayServer  # noqa: E402

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"  [FAIL] {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  [ok] {name}")


class LossyTransport:
    """In-process transport that ALWAYS delivers the packet to the server (so
    the server processes it) but drops the *response* the first time it sees a
    given logical query — simulating a lost ACK that forces exactly one retry.
    Poll/read commands are never dropped, matching what the client retries."""

    RETRYABLE = {protocol.CMD_SEND, protocol.CMD_GROUP_SEND,
                 protocol.CMD_FILE_CHUNK, protocol.CMD_FILE_HEADER,
                 protocol.CMD_REGISTER, protocol.CMD_GETKEY}

    def __init__(self, srv, domain):
        self.srv = srv
        self.domain = domain
        self.dropped = set()
        self.server_hits = {}     # cmd -> how many times the server processed it

    def query(self, labels: list[str]) -> str:
        cmd = labels[0]
        raw = self.srv.handle_query(_build_query(labels, self.domain))  # server processes
        self.server_hits[cmd] = self.server_hits.get(cmd, 0) + 1
        key = tuple(labels)
        if cmd in self.RETRYABLE and key not in self.dropped:
            self.dropped.add(key)
            return 'ERR:timeout'          # response lost → client will retry
        rec = DNSRecord.parse(raw)
        for rr in rec.rr:
            if rr.rtype == QTYPE.TXT:
                return b''.join(rr.rdata.data).decode('utf-8', 'replace')
        return 'ERR:no_response'


def main():
    print("reliability")
    DOMAIN = 'msg.test.local'
    srv = RelayServer(DOMAIN, bind='127.0.0.1', port=0)

    prev = os.getcwd()
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)
    try:
        import web_client
        UM = web_client.UserMessenger

        def mk(name):
            m = UM(name, LossyTransport(srv, DOMAIN))
            ok = m.register()
            return m, ok

        alice, a_ok = mk('alice')
        bob, b_ok = mk('bob')
        check('register succeeds despite a dropped first response', a_ok and b_ok)

        # single-chunk DM — the duplication-prone case (lost final ACK)
        r = alice.send_dm('bob', 'ping')
        check('single-chunk DM reports success after retry', r['ok'])
        # alice's transport had to hit the server at least twice for CMD_SEND
        check('the send was actually retried (server saw it >1x)',
              alice.transport.server_hits.get(protocol.CMD_SEND, 0) >= 2)

        got = bob.poll_dm()
        pings = [m for m in got if m['text'] == 'ping']
        check('recipient gets the message', len(pings) == 1)
        check('message is NOT duplicated by the retry', len(pings) == 1)
        check('a second poll yields nothing more', bob.poll_dm() == [])

        # multi-chunk message (long text spanning several queries)
        big = 'X' * 900
        r = alice.send_dm('bob', big)
        check('multi-chunk DM succeeds through loss', r['ok'])
        got = bob.poll_dm()
        bigs = [m for m in got if m['text'] == big]
        check('multi-chunk message arrives intact exactly once', len(bigs) == 1)

        # direct idempotency probe: replay a completed single-chunk send verbatim
        mid = protocol.gen_msg_id()
        payload = protocol.b32encode(b'0' * 16)
        labels = [protocol.CMD_SEND, 'bob', 'alice', mid, '0', '1'] + \
            protocol.chunk_string(payload, protocol.MAX_LABEL_LEN)
        first = srv.handle_query(_build_query(labels, DOMAIN))
        second = srv.handle_query(_build_query(labels, DOMAIN))   # exact replay
        f1 = _txt(first); f2 = _txt(second)
        check('first delivery is acknowledged', f1 == 'OK:delivered')
        check('verbatim replay is idempotently acked, not re-delivered', f2 == 'OK:delivered')
        # bob must still see only ONE new message from this mid
        got = bob.poll_dm()
        check('replayed mid did not enqueue a duplicate', len(got) <= 1)
    finally:
        os.chdir(prev)

    print(f"\n{passed} passed")


def _txt(raw: bytes) -> str:
    rec = DNSRecord.parse(raw)
    for rr in rec.rr:
        if rr.rtype == QTYPE.TXT:
            return b''.join(rr.rdata.data).decode('utf-8', 'replace')
    return ''


if __name__ == '__main__':
    main()
