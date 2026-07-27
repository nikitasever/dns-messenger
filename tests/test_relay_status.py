"""
/api/relay/status: the real (not decorative) relay-liveness check the login
screen's terminal line reads from.

Rules being tested:
  - relay up -> ok=True with a real, measured latency_ms
  - relay unreachable (nothing bound on the target port) -> ok=False
  - transport not yet configured -> ok=False, no crash
  - unauthenticated by necessity (useful BEFORE login), so it must be rate
    limited per-IP: otherwise an HTTP flood on this route becomes a free UDP
    flood against our own relay — the same class of problem as amplification,
    just with ourselves as the victim instead of a third party.

Run:  python tests/test_relay_status.py
"""
import os
import socket
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import RelayServer          # noqa: E402
from transport import UDPTransport      # noqa: E402

passed = 0


def check(name, cond):
    global passed
    if not cond:
        print(f"  [FAIL] {name}")
        raise SystemExit(1)
    passed += 1
    print(f"  [ok] {name}")


def start_relay(domain):
    srv = RelayServer(domain, bind='127.0.0.1', port=0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]

    def serve():
        while True:
            data, addr = sock.recvfrom(4096)
            if data == b'stop':
                break
            sock.sendto(srv.handle_query(data), addr)

    threading.Thread(target=serve, daemon=True).start()
    return port


def main():
    print("relay_status")
    DOMAIN = 'msg.test.local'

    import web_client as wc
    wc.app.config['TESTING'] = True
    c = wc.app.test_client()

    # ── transport not configured yet ────────────────────────────────────
    wc.transport = None
    r = c.get('/api/relay/status')
    check('no transport configured -> ok=False, no crash', r.get_json().get('ok') is False)

    # ── relay unreachable (bind a socket, then close it so the port is
    #    almost certainly free but nothing answers) ─────────────────────
    dead_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dead_sock.bind(('127.0.0.1', 0))
    dead_port = dead_sock.getsockname()[1]
    dead_sock.close()
    wc.transport = UDPTransport('127.0.0.1', dead_port, DOMAIN)
    wc.transport.sock.settimeout(0.5)   # keep the test fast
    r = c.get('/api/relay/status')
    check('relay unreachable -> ok=False', r.get_json().get('ok') is False)

    # ── relay up ─────────────────────────────────────────────────────────
    port = start_relay(DOMAIN)
    wc.transport = UDPTransport('127.0.0.1', port, DOMAIN)
    r = c.get('/api/relay/status')
    body = r.get_json()
    check('relay up -> ok=True', body.get('ok') is True)
    check('a real latency is measured (not a fixed decorative number)',
          isinstance(body.get('latency_ms'), int) and body['latency_ms'] >= 0)

    # ── rate limiting: this route has no auth gate (needed before login),
    #    so it must not become a free amplifier for flooding our own relay ──
    wc._rate_limit_hits.clear()
    for _ in range(20):
        r = c.get('/api/relay/status')
        check('within budget still answers normally', r.status_code == 200)
    r = c.get('/api/relay/status')
    check('21st request in the window is rate limited', r.status_code == 429)
    wc._rate_limit_hits.clear()

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
