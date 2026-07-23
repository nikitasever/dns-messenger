"""
E2E-шифрование для DNS Messenger.

- X25519        — обмен ключами (ECDH)
- HKDF-SHA256   — вывод симметричного ключа
- ChaCha20-Poly1305 — AEAD-шифрование сообщений

Групповые чаты: используется общий симметричный ключ,
который создатель распространяет членам через ECDH.
"""

import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)

# Длины «сырых» ключей X25519/Ed25519 — оба по 32 байта.
KEY_LEN = 32
SIG_LEN = 64


class Identity:
    """Ключевые пары пользователя: X25519 (шифрование) + Ed25519 (подпись).

    Раздельные ключи по назначению — рекомендация самой X25519/Ed25519:
    один и тот же секрет для ECDH и подписи смешивать нельзя.
    """

    def __init__(self, private_key: X25519PrivateKey | None = None,
                 signing_key: Ed25519PrivateKey | None = None):
        self.private_key = private_key or X25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.signing_key = signing_key or Ed25519PrivateKey.generate()
        self.verify_key = self.signing_key.public_key()

    def public_bytes(self) -> bytes:
        """Только X25519-ключ — для внутреннего ECDH (seal_group_key и т.п.)."""
        return self.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def verify_bytes(self) -> bytes:
        return self.verify_key.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def public_bundle(self) -> bytes:
        """Публичный бандл для распространения: X25519(32) || Ed25519(32)."""
        return self.public_bytes() + self.verify_bytes()

    def private_bytes(self) -> bytes:
        x = self.private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        e = self.signing_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        return x + e

    def save(self, path: str):
        Path(path).write_bytes(self.private_bytes())

    @classmethod
    def load(cls, path: str) -> 'Identity':
        raw = Path(path).read_bytes()
        x_priv = X25519PrivateKey.from_private_bytes(raw[:KEY_LEN])
        if len(raw) >= 2 * KEY_LEN:
            ed_priv = Ed25519PrivateKey.from_private_bytes(raw[KEY_LEN:2 * KEY_LEN])
            return cls(x_priv, ed_priv)
        # Старый файл только с X25519 — доращиваем Ed25519-ключом и апгрейдим
        # файл на диске, чтобы подпись стала стабильной со следующего раза.
        ident = cls(x_priv)
        ident.save(path)
        return ident

    def derive_shared_key(self, peer_public_bytes: bytes) -> bytes:
        """ECDH → HKDF-SHA256 → 32-байт ключ шифрования."""
        peer = X25519PublicKey.from_public_bytes(peer_public_bytes[:KEY_LEN])
        shared = self.private_key.exchange(peer)
        return HKDF(
            algorithm=SHA256(), length=32,
            salt=None, info=b'dns-messenger-v1',
        ).derive(shared)

    def sign(self, data: bytes) -> bytes:
        return self.signing_key.sign(data)


def split_bundle(bundle: bytes) -> tuple[bytes, bytes | None]:
    """Публичный бандл → (X25519, Ed25519|None). None для старых 32-байт ключей."""
    x = bundle[:KEY_LEN]
    ed = bundle[KEY_LEN:2 * KEY_LEN] if len(bundle) >= 2 * KEY_LEN else None
    return x, (ed or None)


def verify_sig(verify_pub: bytes, data: bytes, sig: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(verify_pub).verify(sig, data)
        return True
    except (InvalidSignature, ValueError):
        return False


# ── Подписанная нагрузка ─────────────────────────────────────────────
# Внутри шифротекста лежит: VERSION(1) || Ed25519-подпись(64) || plaintext.
# Подпись покрывает context || plaintext, где context привязывает сообщение к
# заявленному отправителю и адресату (имя_от || 0 || адрес). Это и закрывает
# подмену отправителя в группах: общий групповой ключ расшифрует что угодно,
# но подпись под именем «alice» способна создать только сама alice.
SIGNED_VERSION = 0x01


def build_signed(identity: 'Identity', context: bytes, plaintext: bytes) -> bytes:
    sig = identity.sign(context + plaintext)
    return bytes([SIGNED_VERSION]) + sig + plaintext


def open_signed(blob: bytes, verify_pub: bytes | None, context: bytes) -> tuple[bytes, str]:
    """→ (plaintext, status). status: verified | forged | unverified | unsigned."""
    if blob and blob[0] == SIGNED_VERSION and len(blob) >= 1 + SIG_LEN:
        sig, pt = blob[1:1 + SIG_LEN], blob[1 + SIG_LEN:]
        if verify_pub is None:
            return pt, 'unverified'          # нет ключа отправителя для проверки
        if verify_sig(verify_pub, context + pt, sig):
            return pt, 'verified'
        return pt, 'forged'                  # подпись есть, но не сходится
    return blob, 'unsigned'                  # старый клиент без подписи


# ── Симметричное шифрование ──────────────────────────────────────────

def encrypt(plaintext: bytes, key: bytes) -> bytes:
    """ChaCha20-Poly1305: → nonce(12) || ciphertext || tag(16)."""
    nonce = os.urandom(12)
    return nonce + ChaCha20Poly1305(key).encrypt(nonce, plaintext, None)


def decrypt(data: bytes, key: bytes) -> bytes:
    """ChaCha20-Poly1305: nonce(12) || ciphertext || tag(16) → plaintext."""
    return ChaCha20Poly1305(key).decrypt(data[:12], data[12:], None)


# ── Групповые ключи ─────────────────────────────────────────────────

def generate_group_key() -> bytes:
    """Случайный 32-байт ключ для группового чата."""
    return os.urandom(32)


def seal_group_key(group_key: bytes, my_identity: Identity, peer_public: bytes) -> bytes:
    """Шифрует групповой ключ для конкретного участника (ECDH + ChaCha20)."""
    shared = my_identity.derive_shared_key(peer_public)
    return encrypt(group_key, shared)


def unseal_group_key(sealed: bytes, my_identity: Identity, sender_public: bytes) -> bytes:
    """Расшифровывает групповой ключ, полученный от создателя/инвайтера."""
    shared = my_identity.derive_shared_key(sender_public)
    return decrypt(sealed, shared)
