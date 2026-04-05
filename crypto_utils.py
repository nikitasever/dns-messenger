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

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)


class Identity:
    """Ключевая пара пользователя (X25519)."""

    def __init__(self, private_key: X25519PrivateKey | None = None):
        self.private_key = private_key or X25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()

    def public_bytes(self) -> bytes:
        return self.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def private_bytes(self) -> bytes:
        return self.private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())

    def save(self, path: str):
        Path(path).write_bytes(self.private_bytes())

    @classmethod
    def load(cls, path: str) -> 'Identity':
        return cls(X25519PrivateKey.from_private_bytes(Path(path).read_bytes()))

    def derive_shared_key(self, peer_public_bytes: bytes) -> bytes:
        """ECDH → HKDF-SHA256 → 32-байт ключ шифрования."""
        peer = X25519PublicKey.from_public_bytes(peer_public_bytes)
        shared = self.private_key.exchange(peer)
        return HKDF(
            algorithm=SHA256(), length=32,
            salt=None, info=b'dns-messenger-v1',
        ).derive(shared)


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
