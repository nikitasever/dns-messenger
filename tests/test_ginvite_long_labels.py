"""
Regression: invite_to_group must not blow past DNS's 253-char qname limit
when usernames/group-id approach the UI-imposed ceiling.

Pre-fix qname was:
  <nonce>.i.<gid>.<inviter>.<invited>.<sig_b32(103)>.<sealed_b32(96)>.msg.tunnel.local

With 20-char names and a 20-char gid the whole qname overflows 253 chars,
so dnslib raises DNSLabelError inside _build_query BEFORE the packet is sent
and Flask returns 500. Post-fix the client uses the chunked form 'j' and
splits sig+sealed across multiple round-trips.

Run:  python tests/test_ginvite_long_labels.py
"""
import os
import socket
import sys
import tempfile
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
    return port, srv


def main():
    print("ginvite_long_labels")
    DOMAIN = 'msg.tunnel.local'         # тот же 16-символьный домен, что в проде
    port, srv = start_relay(DOMAIN)

    prev_cwd = os.getcwd()
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)
    try:
        import web_client
        UM = web_client.UserMessenger

        # Имена короткие (у CMD_REGISTER свой overhead: bundle+sig=206 b32
        # символов уже съедают ~210 из 253, поэтому 20-символьные имена
        # ловят ОТДЕЛЬНЫЙ overflow в register — это своя история). А вот у
        # invite длинный gid и обычные короткие имена уже упираются в лимит:
        # sig(103)+sealed(96) при 20-символьном gid overflow'ит qname даже
        # при 5-символьных именах.
        inviter_name = 'alice1'
        invited_name = 'bobbie'
        gid = 'g' * 20

        def mk(name):
            m = UM(name, UDPTransport('127.0.0.1', port, DOMAIN))
            m.register()
            return m

        alice = mk(inviter_name)
        bob = mk(invited_name)

        check('alice creates the group', alice.create_group(gid))
        # Pre-fix это падало DNSLabelError → 500. Post-fix — OK.
        res = alice.invite_to_group(gid, invited_name)
        check(f'long-name invite succeeds (got {res!r})', res.get('ok'))

        bob.fetch_groups()
        check('bob received the group key', gid in bob.group_keys)

        # sanity: обычные короткие имена всё ещё работают
        carol = mk('carol')
        check('short-name invite still works',
              alice.invite_to_group(gid, 'carol')['ok'])
        carol.fetch_groups()
        check('carol received the group key', gid in carol.group_keys)

        # sanity: групповое сообщение проходит round-trip после chunked-invite
        check('alice sends message', alice.send_group(gid, 'hello long names'))
        got = bob.poll_group(gid)
        delivered = [m for m in got if m['text'] == 'hello long names']
        check('bob receives the message', len(delivered) == 1)
        check('message verifies as authentic', delivered[0]['auth'] == 'verified')

        sock_stop = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_stop.sendto(b'stop', ('127.0.0.1', port))
    finally:
        os.chdir(prev_cwd)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
