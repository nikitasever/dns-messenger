"""
Транспортный слой — DNS UDP и DNS-over-HTTPS.

UDP:  клиент → relay-сервер напрямую (для тестов / прямого доступа)
DoH:  клиент → публичный DoH-резолвер → рекурсия → relay-сервер
      Трафик выглядит как обычный HTTPS к разрешённому сервису.
Multi: пробует транспорты по порядку до первого успеха.
"""

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import ssl
from dnslib import DNSRecord, QTYPE, EDNS0

from protocol import gen_nonce

# Клиент анонсирует, что готов принять UDP-ответ до этого размера. Меньше
# усечения (TC=1) и меньше пакетов на крупные TXT (файлы, длинные сообщения).
EDNS_UDP_SIZE = 4096


def _build_query(labels: list[str], domain: str) -> bytes:
    """DNS-запрос TXT с анти-кэш nonce первым лейблом и EDNS0-буфером."""
    qname = gen_nonce() + '.' + '.'.join(labels) + '.' + domain
    rec = DNSRecord.question(qname, 'TXT')
    rec.add_ar(EDNS0(udp_len=EDNS_UDP_SIZE))
    return rec.pack()


class BaseTransport:
    domain: str

    def query(self, labels: list[str]) -> str:
        raise NotImplementedError


class UDPTransport(BaseTransport):
    """Прямой DNS-запрос по UDP."""

    def __init__(self, server_ip: str, server_port: int, domain: str):
        self.server = (server_ip, server_port)
        self.domain = domain

    def query(self, labels: list[str]) -> str:
        # Свой сокет на каждый запрос: UserMessenger используется параллельно
        # (фоновый поток long-poll + запросы из Flask), а recvfrom на общем сокете
        # без корреляции id → ответ уезжает не тому потоку.
        pkt = _build_query(labels, self.domain)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)
        try:
            sock.sendto(pkt, self.server)
            data, _ = sock.recvfrom(EDNS_UDP_SIZE)
            resp = DNSRecord.parse(data)
            for rr in resp.rr:
                if rr.rtype == QTYPE.TXT:
                    return b''.join(rr.rdata.data).decode('utf-8', errors='replace')
        except socket.timeout:
            return 'ERR:timeout'
        except Exception as exc:
            return f'ERR:{exc}'
        finally:
            sock.close()
        return 'ERR:no_response'


class DoHTransport(BaseTransport):
    """DNS-over-HTTPS через публичные резолверы.

    Трафик идёт как HTTPS POST к разрешённому домену (google, yandex и т.д.),
    поэтому проходит через белые списки.
    """

    SERVERS = {
        'google':     'https://dns.google/dns-query',
        'cloudflare': 'https://cloudflare-dns.com/dns-query',
        'yandex':     'https://common.dot.dns.yandex.net/dns-query',
    }

    # DoH-ответ — считанные КБ; больше — вредоносный/битый резолвер, режем.
    MAX_DOH_RESPONSE = 65536

    def __init__(self, domain: str, provider: str = 'google'):
        self.domain = domain
        url = self.SERVERS.get(provider, provider)
        # Кастомный provider (не из белого списка) обязан быть https — иначе
        # urllib сходил бы по file://, http:// на внутренний адрес и т.п. (SSRF).
        if url not in self.SERVERS.values() and not url.startswith('https://'):
            raise ValueError(
                f'DoH provider must be a known key or an https:// URL, got {provider!r}')
        self.url = url
        # create_default_context() проверяет цепочку и имя хоста — сертификаты
        # НЕ принимаются вслепую (прежний комментарий про «отладку» был неверен).
        self._ctx = ssl.create_default_context()

    def query(self, labels: list[str]) -> str:
        pkt = _build_query(labels, self.domain)
        req = urllib.request.Request(
            self.url,
            data=pkt,
            headers={
                'Content-Type': 'application/dns-message',
                'Accept': 'application/dns-message',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=10, context=self._ctx) as resp:
                # Резолвер untrusted: читаем не больше лимита, иначе он мог бы
                # отдать гигабайтное тело и выесть память клиента.
                data = resp.read(self.MAX_DOH_RESPONSE + 1)
            if len(data) > self.MAX_DOH_RESPONSE:
                return 'ERR:doh_response_too_large'
            dns_resp = DNSRecord.parse(data)
            for rr in dns_resp.rr:
                if rr.rtype == QTYPE.TXT:
                    return b''.join(rr.rdata.data).decode('utf-8', errors='replace')
        except Exception as exc:
            return f'ERR:{exc}'
        return 'ERR:no_response'


class YandexDiskTransport(BaseTransport):
    """Covert-канал поверх Яндекс.Диска — на случай, когда прямой DNS/DoH к
    relay недоступен (например, режим «белого списка»), а cloud-api.yandex.net
    остаётся разрешённым.

    Никакой новой протокольной логики: содержимое загружаемых файлов — это
    те же самые сырые DNS wire-байты, что и в UDPTransport/DoHTransport,
    просто вместо UDP/HTTPS-к-резолверу они кладутся файлом в папку
    приложения на Диске и оттуда же читается ответ. Мост на стороне relay
    (disk_bridge.py) скармливает эти байты тому же RelayServer.handle_query()
    без изменений.

    Асимметрично: клиент ПИШЕТ запрос в свою папку своим OAuth-токеном, но
    ЧИТАЕТ ответ из чужой (мостовой) папки БЕЗ токена — по её публичному
    ключу (см. proверку в docs/traffic-analysis-plan.md). Публичный ключ
    моста — bootstrap-константа, распространяется так же, как domain.
    """

    API = 'https://cloud-api.yandex.net/v1/disk'
    POLL_INTERVAL = 2.0
    POLL_TIMEOUT = 25.0

    def __init__(self, domain: str, username: str, oauth_token: str, bridge_public_key: str):
        self.domain = domain
        self.username = username
        self.token = oauth_token
        self.bridge_public_key = bridge_public_key
        self._published = False

    def _req(self, method: str, url: str, headers: dict | None = None,
              data: bytes | None = None) -> tuple[int, bytes]:
        req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def _ensure_published(self):
        if self._published:
            return
        auth = {'Authorization': f'OAuth {self.token}'}
        # Идемпотентно: если папки/публикации ещё нет, API их создаёт;
        # если уже есть — просто отвечает 200/409, оба случая ОК.
        self._req('PUT', f'{self.API}/resources?path=app:/', headers=auth)
        self._req('PUT', f'{self.API}/resources/publish?path=app:/', headers=auth)
        self._published = True

    def _upload(self, name: str, payload: bytes) -> bool:
        auth = {'Authorization': f'OAuth {self.token}'}
        path = urllib.parse.quote(f'app:/{name}')
        status, body = self._req(
            'GET', f'{self.API}/resources/upload?path={path}&overwrite=true', headers=auth)
        if status != 200:
            return False
        href = json.loads(body)['href']
        status, _ = self._req('PUT', href, data=payload)
        return status in (201, 202)

    def _download_public(self, path_in_bridge: str) -> bytes | None:
        pk = urllib.parse.quote(self.bridge_public_key, safe='')
        p = urllib.parse.quote(path_in_bridge)
        status, body = self._req(
            'GET', f'{self.API}/public/resources?public_key={pk}&path={p}')
        if status != 200:
            return None
        meta = json.loads(body)
        href = meta.get('file')
        if not href:
            return None
        status, content = self._req('GET', href)
        return content if status == 200 else None

    def query(self, labels: list[str]) -> str:
        self._ensure_published()
        pkt = _build_query(labels, self.domain)
        req_id = gen_nonce()
        qname = f'q_{req_id}.bin'
        rname = f'r_{self.username}_{req_id}.bin'
        if not self._upload(qname, pkt):
            return 'ERR:disk_upload_failed'

        deadline = time.time() + self.POLL_TIMEOUT
        while time.time() < deadline:
            data = self._download_public(f'/{rname}')
            if data is not None:
                try:
                    resp = DNSRecord.parse(data)
                    for rr in resp.rr:
                        if rr.rtype == QTYPE.TXT:
                            return b''.join(rr.rdata.data).decode('utf-8', errors='replace')
                except Exception as exc:
                    return f'ERR:{exc}'
            time.sleep(self.POLL_INTERVAL)
        return 'ERR:timeout'


class MultiTransport(BaseTransport):
    """Пробует транспорты по очереди до первого успешного ответа."""

    def __init__(self, transports: list[BaseTransport]):
        self.transports = transports
        self.domain = transports[0].domain if transports else ''

    def query(self, labels: list[str]) -> str:
        last = 'ERR:no_transports'
        for t in self.transports:
            result = t.query(labels)
            if not result.startswith('ERR'):
                return result
            last = result
        return last
