"""
Транспортный слой — DNS UDP и DNS-over-HTTPS.

UDP:  клиент → relay-сервер напрямую (для тестов / прямого доступа)
DoH:  клиент → публичный DoH-резолвер → рекурсия → relay-сервер
      Трафик выглядит как обычный HTTPS к разрешённому сервису.
Multi: пробует транспорты по порядку до первого успеха.
"""

import socket
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
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(5.0)

    def query(self, labels: list[str]) -> str:
        pkt = _build_query(labels, self.domain)
        try:
            self.sock.sendto(pkt, self.server)
            data, _ = self.sock.recvfrom(EDNS_UDP_SIZE)
            resp = DNSRecord.parse(data)
            for rr in resp.rr:
                if rr.rtype == QTYPE.TXT:
                    return b''.join(rr.rdata.data).decode('utf-8', errors='replace')
        except socket.timeout:
            return 'ERR:timeout'
        except Exception as exc:
            return f'ERR:{exc}'
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
