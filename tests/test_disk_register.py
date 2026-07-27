"""
Disk-канал: регистрация public_key (Phase C of docs/traffic-analysis-plan.md).

Same shape as test_group_rekey.py: a real in-process RelayServer driven by
an actual UserMessenger, so the multi-query chunking (register_disk_pubkey),
server-side reassembly (_h_diskreg), the registry readout (CMD_DISK_LIST /
_h_disklist), and disk_bridge.fetch_registry() are all exercised together,
not just isolated primitives. No real Yandex.Disk calls — that part is
verified separately and manually (see docs/traffic-analysis-plan.md).

Run:  python tests/test_disk_register.py
"""
import base64
import os
import socket
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protocol import CMD_DISK_REGISTER, b32encode, b32decode, chunk_string, MAX_LABEL_LEN  # noqa: E402
from server import RelayServer  # noqa: E402
from transport import UDPTransport  # noqa: E402
import disk_bridge  # noqa: E402

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
    print("disk pubkey registration")
    DOMAIN = 'msg.test.local'
    port, srv = start_relay(DOMAIN)

    prev_cwd = os.getcwd()
    tmp = tempfile.mkdtemp()
    os.chdir(tmp)
    try:
        import web_client
        UM = web_client.UserMessenger

        alice = UM('alice', UDPTransport('127.0.0.1', port, DOMAIN))
        check('alice registers (pinned)', alice.register())

        # Реалистичная длина: Яндекс.Диск отдаёт стандартный base64 от ~64
        # сырых байт (тот самый случай, который не влезал в один DNS-запрос
        # до чанкования).
        fake_pubkey = base64.b64encode(os.urandom(64)).decode('ascii')
        check('register_disk_pubkey succeeds (multi-chunk over DNS labels)',
              alice.register_disk_pubkey(fake_pubkey))

        with srv.lock:
            check("relay stored the EXACT pubkey string (round-trips byte-for-byte)",
                  srv.users['alice']['disk_pubkey'] == fake_pubkey)

        # ── CMD_DISK_LIST отдаёт то же значение ──────────────────────────
        raw = alice._q(['z'])
        check('CMD_DISK_LIST responds OK:...', raw.startswith('OK:'))
        entry = dict(e.split(':', 1) for e in raw[len('OK:'):].split(','))
        check('registry contains alice', 'alice' in entry)
        check('registry pubkey decodes back to the exact original string',
              b32decode(entry['alice']).decode('utf-8') == fake_pubkey)

        # ── disk_bridge.fetch_registry() видит то же самое ───────────────
        reg = disk_bridge.fetch_registry(DOMAIN, ('127.0.0.1', port))
        check('fetch_registry returns alice -> exact pubkey',
              reg.get('alice') == fake_pubkey)

        # ── ре-регистрация перезаписывает (не дублирует) ─────────────────
        fake_pubkey2 = base64.b64encode(os.urandom(64)).decode('ascii')
        check('re-registration with a new key succeeds',
              alice.register_disk_pubkey(fake_pubkey2))
        with srv.lock:
            check("relay now holds the NEW key, not the old one",
                  srv.users['alice']['disk_pubkey'] == fake_pubkey2)

        # ── незакреплённое (анонимное) имя не может зарегистрировать ─────
        mallory = UM('mallory', UDPTransport('127.0.0.1', port, DOMAIN))
        # Анонимный клиент никогда не подписывал регистрацию — 'mallory' в
        # self.users вообще не существует у релея, entry is None -> unpinned.
        resp = mallory._q([CMD_DISK_REGISTER, 'mallory', '0', '1',
                            b32encode(os.urandom(10))])
        check('unpinned/unknown user is rejected', resp == 'ERR:unpinned')

        # ── подделанная подпись на финальном чанке отклоняется ───────────
        garbage_pubkey = base64.b64encode(os.urandom(64)).decode('ascii')
        raw_chunks = chunk_string(b32encode(base64.b64decode(garbage_pubkey)), MAX_LABEL_LEN)
        n = len(raw_chunks)
        for seq, c in enumerate(raw_chunks[:-1]):
            check(f'forged attempt: intermediate chunk {seq} accepted',
                  alice._q([CMD_DISK_REGISTER, 'alice', str(seq), str(n), c]) == 'OK:chunk')
        garbage_sig_chunks = chunk_string(b32encode(bytes(64)), MAX_LABEL_LEN)
        forged = alice._q([CMD_DISK_REGISTER, 'alice', str(n - 1), str(n), raw_chunks[-1],
                            'somenonce', '9999999999'] + garbage_sig_chunks)
        check('forged signature on final chunk is rejected', forged == 'ERR:auth')
        with srv.lock:
            check("forged attempt did NOT overwrite alice's real key",
                  srv.users['alice']['disk_pubkey'] == fake_pubkey2)

        sock_stop = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_stop.sendto(b'stop', ('127.0.0.1', port))
    finally:
        os.chdir(prev_cwd)

    print(f"\n{passed} passed")


if __name__ == '__main__':
    main()
