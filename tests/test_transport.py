"""
Tests for the anti-cache nonce + EDNS0 transport changes (v2 stealth).

Drives a real RelayServer through UDPTransport in-process, so the nonce
stripping, EDNS0 round-trip and unchanged command semantics are all exercised
end to end rather than mocked.

Run:  python tests/test_transport.py
"""
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dnslib import DNSRecord, QTYPE  # noqa: E402

import protocol  # noqa: E402
import transport as transport_mod  # noqa: E402
from transport import UDPTransport, _build_query  # noqa: E402
from server import RelayServer  # noqa: E402

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"  [FAIL] {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  [ok] {name}")


def main():
    print("transport")

    DOMAIN = 'msg.test.local'

    # ── nonce ───────────────────────────────────────────────────────────
    n1, n2 = protocol.gen_nonce(), protocol.gen_nonce()
    check('nonce has the declared length', len(n1) == protocol.NONCE_LEN)
    check('nonce is DNS-label-safe', n1.isalnum() and n1.islower())
    check('nonces differ between calls', n1 != n2)

    # ── query framing: nonce first, EDNS0 present ───────────────────────
    raw = _build_query(['p', 'alice', 'tok'], DOMAIN)
    rec = DNSRecord.parse(raw)
    qname = str(rec.q.qname).rstrip('.')
    check('query targets a TXT record', rec.q.qtype == QTYPE.TXT)
    check('nonce is prepended as the first label',
          qname.split('.')[0] != 'p' and qname.split('.')[1] == 'p')
    check('qname still ends with cmd+params+domain', qname.endswith(f'p.alice.tok.{DOMAIN}'))
    check('EDNS0 OPT is attached', len(rec.ar) == 1)
    check('EDNS0 advertises the large buffer',
          getattr(rec.ar[0], 'edns_len', None) == transport_mod.EDNS_UDP_SIZE)

    # two consecutive queries must differ (uncacheable)
    q_a = str(DNSRecord.parse(_build_query(['p', 'alice', 'tok'], DOMAIN)).q.qname)
    q_b = str(DNSRecord.parse(_build_query(['p', 'alice', 'tok'], DOMAIN)).q.qname)
    check('identical logical query yields distinct qnames', q_a != q_b)

    # ── server strips the nonce and still dispatches ────────────────────
    srv = RelayServer(DOMAIN, bind='127.0.0.1', port=0)
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 0))
    srv_port = sock.getsockname()[1]

    def serve():
        while True:
            data, addr = sock.recvfrom(4096)
            if data == b'stop':
                break
            sock.sendto(srv.handle_query(data), addr)

    t = threading.Thread(target=serve, daemon=True)
    t.start()

    client = UDPTransport('127.0.0.1', srv_port, DOMAIN)

    # register → getkey round-trip proves the nonce'd path reaches the handler
    pub = protocol.b32encode(os.urandom(32))
    res = client.query([protocol.CMD_REGISTER, 'alice'] + protocol.chunk_string(pub, protocol.MAX_LABEL_LEN))
    check('register succeeds through a nonce+EDNS0 query', res.startswith('OK'))

    res = client.query([protocol.CMD_GETKEY, 'alice'])
    check('getkey returns the stored key', res.startswith('KEY:') and pub in res)

    # poll on an empty mailbox
    res = client.query([protocol.CMD_POLL, 'alice', '0'])
    check('poll of empty mailbox says EMPTY', res == 'EMPTY')

    # a legacy query WITHOUT a nonce (first label is a real command) still works
    legacy = DNSRecord.question(f'{protocol.CMD_GETKEY}.alice.{DOMAIN}', 'TXT').pack()
    reply = DNSRecord.parse(srv.handle_query(legacy))
    txt = b''.join(reply.rr[0].rdata.data).decode()
    check('legacy nonce-less query is still dispatched', txt.startswith('KEY:'))

    # server reply advertises EDNS0 and TTL=0
    probe = _build_query([protocol.CMD_GETKEY, 'alice'], DOMAIN)
    reply = DNSRecord.parse(srv.handle_query(probe))
    check('server reply carries an EDNS0 OPT', len(reply.ar) == 1)
    check('server reply keeps TTL=0 (anti-cache)', reply.rr[0].ttl == 0)

    sock.sendto(b'stop', ('127.0.0.1', srv_port))

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
