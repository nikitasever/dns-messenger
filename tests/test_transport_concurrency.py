"""
Regression test for the UDPTransport response-crosstalk race.

Before the fix, UDPTransport held one shared socket per instance and
performed sendto+recvfrom on it. When two threads called .query() at once
(fact of life for a UserMessenger: background poll_dm/poll_group/poll_files
loop + Flask-request handlers on the same messenger), thread A could
recvfrom() the response destined for thread B and vice versa — because
DNS queries carry a transaction id but this code never checked it, and
there was no request/response correlation of any kind.

This test fires many concurrent queries against a real in-process
RelayServer from many threads and asserts every caller gets back its own
answer, not somebody else's.

Run:  python tests/test_transport_concurrency.py
"""
import os
import socket
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import protocol  # noqa: E402
from transport import UDPTransport  # noqa: E402
from server import RelayServer  # noqa: E402

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
    return port, sock


def main():
    print("transport_concurrency")

    DOMAIN = 'msg.test.local'
    port, stop_sock = start_relay(DOMAIN)

    client = UDPTransport('127.0.0.1', port, DOMAIN)

    # Register N distinct users, each with a distinct public-key blob, so
    # every getkey response is unique — if any thread receives a peer's
    # answer instead of its own, the assertion below fires.
    N = 12
    ITERS = 20
    users = [f'user{i}' for i in range(N)]
    pubs = {u: protocol.b32encode(os.urandom(32)) for u in users}
    for u in users:
        res = client.query(
            [protocol.CMD_REGISTER, u]
            + protocol.chunk_string(pubs[u], protocol.MAX_LABEL_LEN))
        assert res.startswith('OK'), res

    errors: list[str] = []
    err_lock = threading.Lock()
    barrier = threading.Barrier(N)

    def hammer(u):
        # Line every thread up on the barrier so their first-round sends
        # actually overlap on the wire — the race needs concurrent recvfrom
        # calls on the shared socket to bite.
        barrier.wait()
        for _ in range(ITERS):
            res = client.query([protocol.CMD_GETKEY, u])
            if not res.startswith('KEY:'):
                with err_lock:
                    errors.append(f'{u}: bad reply shape {res!r}')
                return
            if pubs[u] not in res:
                with err_lock:
                    # This is the crosstalk signature: valid KEY: reply,
                    # but the key belongs to somebody else.
                    errors.append(f'{u}: got someone else\'s key back ({res!r})')
                return

    threads = [threading.Thread(target=hammer, args=(u,)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    check('no thread received another thread\'s response', not errors)
    if errors:
        for e in errors[:5]:
            print('   ', e)

    stop_sock.sendto(b'stop', ('127.0.0.1', port))
    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
