"""
Web Push (RFC 8030 / 8188 / 8291 / 8292) на голом `cryptography`.

Зачем свой велосипед вместо pywebpush: тот тянет aiohttp + http-ece, а здесь
уже есть `cryptography`, и всё нужное — ECDH P-256, HKDF-SHA256, AES-128-GCM,
ECDSA — в ней есть. Ноль новых зависимостей, что для оффлайн-развёртывания
этого мессенджера существеннее удобства.

Публичный API:
    keys = load_or_create_vapid(Path('.messenger_vapid.json'))
    send_push(subscription, payload_bytes, keys, sub='mailto:...')
"""

import base64
import ipaddress
import json
import os
import socket
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

CURVE = ec.SECP256R1()
# Записи RFC 8188; одна запись на сообщение, полезная нагрузка заведомо мала.
RECORD_SIZE = 4096
DEFAULT_TTL = 86400


# ─── base64url без паддинга ──────────────────────────────────────────────

def b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def b64u_decode(data: str) -> bytes:
    if isinstance(data, bytes):
        data = data.decode('ascii')
    return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))


# ─── VAPID-ключи ─────────────────────────────────────────────────────────

def generate_vapid() -> dict:
    """Новая пара VAPID-ключей. Возвращает {'private': b64u, 'public': b64u}."""
    priv = ec.generate_private_key(CURVE)
    private_raw = priv.private_numbers().private_value.to_bytes(32, 'big')
    public_raw = priv.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    return {'private': b64u_encode(private_raw), 'public': b64u_encode(public_raw)}


def load_or_create_vapid(path: Path) -> dict:
    """Прочитать пару ключей с диска, создав её при первом запуске.

    Ключи должны пережить перезапуск: браузерные подписки привязаны к
    applicationServerKey, и новая пара разом инвалидирует их все.
    """
    if path.exists():
        try:
            data = json.loads(path.read_text('utf-8'))
            if data.get('private') and data.get('public'):
                return data
        except Exception:
            pass
    keys = generate_vapid()
    path.write_text(json.dumps(keys, indent=2), 'utf-8')
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows/иные ФС — не критично
    return keys


def _vapid_private_key(keys: dict) -> ec.EllipticCurvePrivateKey:
    value = int.from_bytes(b64u_decode(keys['private']), 'big')
    return ec.derive_private_key(value, CURVE)


# ─── VAPID JWT (RFC 8292) ────────────────────────────────────────────────

def _vapid_auth_header(endpoint: str, keys: dict, sub: str) -> str:
    parts = urllib.parse.urlsplit(endpoint)
    aud = f'{parts.scheme}://{parts.netloc}'
    header = {'typ': 'JWT', 'alg': 'ES256'}
    claims = {'aud': aud, 'exp': int(time.time()) + 12 * 3600, 'sub': sub}
    signing_input = (
        b64u_encode(json.dumps(header, separators=(',', ':')).encode()) + '.' +
        b64u_encode(json.dumps(claims, separators=(',', ':')).encode())
    ).encode('ascii')

    der = _vapid_private_key(keys).sign(signing_input, ec.ECDSA(hashes.SHA256()))
    # JWS требует «сырую» подпись r||s, а cryptography отдаёт DER.
    r, s = asym_utils.decode_dss_signature(der)
    raw_sig = r.to_bytes(32, 'big') + s.to_bytes(32, 'big')

    jwt = signing_input.decode('ascii') + '.' + b64u_encode(raw_sig)
    return f"vapid t={jwt}, k={keys['public']}"


# ─── Шифрование содержимого (aes128gcm, RFC 8291) ────────────────────────

def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length,
                salt=salt, info=info).derive(ikm)


def encrypt_payload(payload: bytes, ua_public_raw: bytes, auth_secret: bytes) -> bytes:
    """Зашифровать тело в формате aes128gcm. Возвращает готовое тело запроса."""
    as_private = ec.generate_private_key(CURVE)
    as_public_raw = as_private.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    ua_public = ec.EllipticCurvePublicKey.from_encoded_point(CURVE, ua_public_raw)
    shared = as_private.exchange(ec.ECDH(), ua_public)

    # RFC 8291 §3.4: сначала общий PRK на auth-секрете подписки…
    auth_info = b'WebPush: info\x00' + ua_public_raw + as_public_raw
    prk = _hkdf(auth_secret, shared, auth_info, 32)

    # …затем из него ключ и nonce, посоленные случайной солью записи.
    salt = os.urandom(16)
    cek = _hkdf(salt, prk, b'Content-Encoding: aes128gcm\x00', 16)
    nonce = _hkdf(salt, prk, b'Content-Encoding: nonce\x00', 12)

    # 0x02 — разделитель последней записи (RFC 8188 §2).
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b'\x02', None)

    # Заголовок: salt(16) | rs(4) | idlen(1) | ключ отправителя(65)
    header = salt + struct.pack('!IB', RECORD_SIZE, len(as_public_raw)) + as_public_raw
    return header + ciphertext


# ─── Отправка ────────────────────────────────────────────────────────────

class UnsafeEndpoint(Exception):
    """Endpoint отклонён проверкой SSRF (не https или указывает на приватный/
    локальный адрес)."""


def is_safe_push_endpoint(url: str) -> bool:
    """SSRF-заслон: subscription.endpoint приходит от клиента без ограничений
    (это его законное поле — у каждого push-провайдера свой домен), и без
    проверки сервер по нему сходит сам через send_push. Без заслона любой
    залогиненный пользователь мог бы подписаться на 169.254.169.254 (облачные
    метаданные), localhost-сервисы или внутреннюю сеть и получить сервер как
    прокси, читая результат через /api/push/test.

    Требует https и резолвит хост, отклоняя loopback/private/link-local/
    reserved/multicast адреса. Не защищает от DNS rebinding (хост резолвится
    в безопасный IP на момент проверки, а на момент реального запроса — в
    другой): для push-endpoint'ов подставных провайдеров это принятый разумный
    компромисс, а не полноценная защита уровня "connect только на запиненный IP".
    """
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for _family, _type, _proto, _canon, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or
                ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


class PushGone(Exception):
    """Подписка мертва (404/410) — вызывающий код должен её удалить."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Не следовать за редиректами при отправке push.

    is_safe_push_endpoint проверяет ТОЛЬКО исходный endpoint. urllib с дефолтным
    opener'ом молча идёт по 3xx-редиректу без повторной проверки, поэтому
    вредоносный push-сервер (прошедший проверку как публичный HTTPS) мог ответить
    `302 Location: http://169.254.169.254/…` и увести запрос на внутренний адрес —
    SSRF в обход заслона. Push-endpoint'ы по RFC 8030 — прямые POST-цели и не
    должны редиректить, поэтому просто отказываемся следовать.
    """
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_push_opener = urllib.request.build_opener(_NoRedirect)


def send_push(subscription: dict, payload: bytes, keys: dict,
              sub: str = 'mailto:admin@localhost', ttl: int = DEFAULT_TTL,
              timeout: float = 10.0) -> int:
    """Отправить одно push-сообщение. Возвращает HTTP-статус.

    Бросает PushGone, если push-сервис сообщил, что подписки больше нет.
    """
    endpoint = subscription['endpoint']
    if not is_safe_push_endpoint(endpoint):
        raise UnsafeEndpoint(f'refusing to push to {endpoint!r}')
    dh = subscription.get('keys', {})
    body = encrypt_payload(payload, b64u_decode(dh['p256dh']), b64u_decode(dh['auth']))

    req = urllib.request.Request(endpoint, data=body, method='POST')
    req.add_header('Content-Encoding', 'aes128gcm')
    req.add_header('Content-Type', 'application/octet-stream')
    # urllib нормализует имя в 'Ttl'; заголовки HTTP регистронезависимы (RFC 7230),
    # push-сервисы это принимают — не «чинить» на ручную сборку заголовков.
    req.add_header('TTL', str(ttl))
    req.add_header('Urgency', 'high')
    req.add_header('Authorization', _vapid_auth_header(endpoint, keys, sub))

    try:
        # Свой opener без следования редиректам (см. _NoRedirect): закрывает
        # SSRF через 3xx-увод на внутренний адрес после прохождения заслона.
        with _push_opener.open(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            raise PushGone(f'subscription gone ({e.code})') from e
        raise
