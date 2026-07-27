"""
Мост между Яндекс.Диском и настоящим relay — запасной covert-транспорт на
случай, когда прямой DNS/DoH к relay недоступен (см.
docs/traffic-analysis-plan.md), а cloud-api.yandex.net остаётся доступным.

ВАЖНО: RelayServer хранит все данные (аккаунты, почту, группы) только в
памяти процесса, без персистентности на диск. Поэтому мост НЕ создаёт свой
RelayServer — это был бы полностью отдельный, пустой «двойник», сообщения
через который никогда не долетали бы до реальных получателей. Вместо этого
мост пересылает сырые DNS wire-байты уже РАБОТАЮЩЕМУ relay-процессу по
loopback UDP — точно так же, как это делает обычный клиент через
UDPTransport, только источник запроса — файл на Диске, а не сеть.

Реестр клиентов (кто на какой публичный ключ своей папки на Диске пишет
запросы) сейчас читается из простого JSON-файла — задача автоматической
регистрации через сам протокол (см. план) вынесена за рамки прототипа.

Запуск:  python disk_bridge.py --relay-host 127.0.0.1 --relay-port 15353 \
             --clients disk_bridge_clients.json
(укажи --relay-port тот же, что RELAY_PORT в systemd-юните relay-процесса —
мост должен слать на порт УЖЕ ЗАПУЩЕННОГО relay, не поднимать новый).
Требует переменную окружения YANDEX_DISK_TOKEN — OAuth-токен папки приложения
моста (именно моста, не клиентов).

Формат disk_bridge_clients.json:
  {"alice": {"public_key": "<public_key папки Алисы>"}, ...}
"""

import argparse
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

API = 'https://cloud-api.yandex.net/v1/disk'
POLL_INTERVAL = 3.0


def _req(method, url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:
        return 0, str(exc).encode()


def ensure_published(token):
    auth = {'Authorization': f'OAuth {token}'}
    _req('PUT', f'{API}/resources?path=app:/', headers=auth)
    status, body = _req('PUT', f'{API}/resources/publish?path=app:/', headers=auth)
    status, body = _req('GET', f'{API}/resources?path=app:/', headers=auth)
    if status != 200:
        raise RuntimeError(f'bridge: cannot read own app folder: {status} {body!r}')
    meta = json.loads(body)
    return meta['public_key']


def list_client_queries(client_public_key, seen: set) -> list[str]:
    """Имена новых (ещё не обработанных) q_*.bin в публичной папке клиента."""
    pk = urllib.parse.quote(client_public_key, safe='')
    status, body = _req('GET', f'{API}/public/resources?public_key={pk}&sort=-created&limit=50')
    if status != 200:
        return []
    meta = json.loads(body)
    items = meta.get('_embedded', {}).get('items', [])
    return [it['name'] for it in items
            if it['name'].startswith('q_') and it['name'].endswith('.bin')
            and it['name'] not in seen]


def download_public(client_public_key, name) -> bytes | None:
    pk = urllib.parse.quote(client_public_key, safe='')
    p = urllib.parse.quote('/' + name)
    status, body = _req('GET', f'{API}/public/resources?public_key={pk}&path={p}')
    if status != 200:
        return None
    href = json.loads(body).get('file')
    if not href:
        return None
    status, content = _req('GET', href)
    return content if status == 200 else None


def upload_own(token, name, payload) -> bool:
    auth = {'Authorization': f'OAuth {token}'}
    path = urllib.parse.quote(f'app:/{name}')
    status, body = _req('GET', f'{API}/resources/upload?path={path}&overwrite=true', headers=auth)
    if status != 200:
        return False
    href = json.loads(body)['href']
    status, _ = _req('PUT', href, data=payload)
    return status in (201, 202)


def forward_to_relay(relay_addr, pkt: bytes) -> bytes | None:
    """Пересылает сырые DNS wire-байты уже работающему relay по loopback UDP
    и возвращает его ответ — это ровно то, что делает UDPTransport.query(),
    только без собственного построения пакета (он уже готов)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5.0)
    try:
        sock.sendto(pkt, relay_addr)
        data, _ = sock.recvfrom(65536)
        return data
    except socket.timeout:
        return None
    finally:
        sock.close()


def main():
    ap = argparse.ArgumentParser(description='Yandex.Disk cover-channel bridge')
    ap.add_argument('--relay-host', default='127.0.0.1')
    ap.add_argument('--relay-port', type=int, required=True,
                     help='порт УЖЕ ЗАПУЩЕННОГО relay-процесса (RELAY_PORT из systemd-юнита)')
    ap.add_argument('--clients', default='disk_bridge_clients.json')
    args = ap.parse_args()
    relay_addr = (args.relay_host, args.relay_port)

    token = os.environ.get('YANDEX_DISK_TOKEN')
    if not token:
        raise SystemExit('YANDEX_DISK_TOKEN env var is required')

    own_public_key = ensure_published(token)
    print(f'[*] bridge own public_key = {own_public_key}', flush=True)
    print(f'[*] forwarding to relay at {relay_addr}', flush=True)

    seen_per_client: dict[str, set] = {}

    while True:
        try:
            with open(args.clients, encoding='utf-8') as f:
                clients = json.load(f)
        except FileNotFoundError:
            clients = {}

        for username, info in clients.items():
            cpk = info.get('public_key')
            if not cpk:
                continue
            seen = seen_per_client.setdefault(username, set())
            for name in list_client_queries(cpk, seen):
                seen.add(name)
                pkt = download_public(cpk, name)
                if pkt is None:
                    continue
                req_id = name[len('q_'):-len('.bin')]
                resp = forward_to_relay(relay_addr, pkt)
                if resp is None:
                    print(f'[!] {username}/{name}: relay timeout', flush=True)
                    continue
                rname = f'r_{username}_{req_id}.bin'
                if upload_own(token, rname, resp):
                    print(f'[*] {username}: {name} -> {rname}', flush=True)
                else:
                    print(f'[!] {username}: upload of {rname} failed', flush=True)

        time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    main()
