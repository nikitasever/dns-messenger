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
from dnslib import DNSRecord, QTYPE


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
        qname = '.'.join(labels) + '.' + self.domain
        pkt = DNSRecord.question(qname, 'TXT').pack()
        try:
            self.sock.sendto(pkt, self.server)
            data, _ = self.sock.recvfrom(4096)
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

    def __init__(self, domain: str, provider: str = 'google'):
        self.domain = domain
        self.url = self.SERVERS.get(provider, provider)
        # Разрешаем все сертификаты для отладки (в проде — убрать)
        self._ctx = ssl.create_default_context()

    def query(self, labels: list[str]) -> str:
        qname = '.'.join(labels) + '.' + self.domain
        pkt = DNSRecord.question(qname, 'TXT').pack()
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
                data = resp.read()
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
