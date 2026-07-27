"""
X3DH key agreement + Double Ratchet — forward secrecy and post-compromise
security for 1:1 DMs. Phase 1 of docs/ratchet-plan.md.

Scope, on purpose:
- Groups are NOT covered here — see the plan's Phase 4 (Sender Keys). Group
  chats keep using the old static-key scheme in crypto_utils.seal_group_key
  for now.
- Ratchet state CAN be persisted across restarts (Phase 2 of the plan) via
  RatchetSession.to_dict()/from_dict() + web_client.py's
  save_ratchet_state()/load_all_ratchet_states(). The storage key is derived
  from the already-decrypted Identity, not the account password directly
  (see ratchet_storage_key()) — the password itself is never retained beyond
  the moment UserMessenger decrypts identity.key/prekeys.key.
- No header encryption (the DH public key / counters that prefix each
  ciphertext travel in the clear, as in the original Double Ratchet spec
  before Signal's later "Sesame" header-encryption extension). The header is
  authenticated as AAD, so tampering with it fails the AEAD tag rather than
  silently steering decryption at the wrong key — it just isn't hidden from
  an observer. Out of scope for phase 1; revisit if traffic analysis
  resistance work ever happens.

Why X3DH at all, not just a live Diffie-Hellman handshake: recipients are
routinely offline (see web_client.py's msg_buffer store-and-forward), so the
sender must be able to compute the initial shared secret alone, using only a
prekey bundle the recipient published in advance. That's exactly what X3DH
is for.
"""
import base64
import hmac
import os
import struct

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)

from crypto_utils import Identity, verify_sig, encrypt, decrypt

KEY_LEN = 32
# Пропущенных ключей цепочки на сессию (пара собеседников) — не больше этого.
# Без лимита сообщение с искусственно завышенным номером в заголовке заставило
# бы жертву насчитать и захранить неограниченное количество неиспользуемых
# ключей (DoS по памяти). Тот же порядок величины, что и msg_buffer cap (500)
# в web_client.py.
MAX_SKIPPED_KEYS = 1000


class RatchetError(Exception):
    """Ratchet-операция не может быть выполнена (испорченные данные, лимит,
    неверная подпись prekey и т.п.) — вызывающий код обязан её ловить, как и
    любую другую ошибку расшифровки."""


# ═══════════════════════════════════════════════════════════════════════
# X3DH — начальное согласование секрета, работает даже если получатель офлайн
# ═══════════════════════════════════════════════════════════════════════

def generate_prekey_pair() -> X25519PrivateKey:
    return X25519PrivateKey.generate()


def prekey_public_bytes(prekey: X25519PrivateKey) -> bytes:
    return prekey.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def prekey_private_bytes(prekey: X25519PrivateKey) -> bytes:
    """Для персистентности на диске (см. web_client.save_prekey_store) — в
    памяти prekeys всегда живут как объекты X25519PrivateKey, не как байты."""
    return prekey.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())


def prekey_from_private_bytes(data: bytes) -> X25519PrivateKey:
    return X25519PrivateKey.from_private_bytes(data)


def sign_prekey(identity: Identity, prekey_public: bytes) -> bytes:
    """Подпись identity-ключом поверх публичной половины signed prekey —
    без неё сервер (или кто угодно на пути) мог бы подсунуть отправителю
    чужой prekey под видом бандла получателя, подменив X3DH секрет целиком."""
    return identity.sign(prekey_public)


def _dh(priv: X25519PrivateKey, pub_bytes: bytes) -> bytes:
    return priv.exchange(X25519PublicKey.from_public_bytes(pub_bytes))


def _x3dh_kdf(material: bytes) -> bytes:
    # 32 байта 0xFF перед секретом — стандартная предосторожность X3DH: не
    # даёт секрету начаться с последовательности, которая могла бы быть
    # валидной X25519-точкой, и отделяет этот вывод от прочих применений HKDF.
    return HKDF(algorithm=SHA256(), length=32, salt=b'\x00' * 32,
                info=b'dns-messenger-x3dh-v1').derive(b'\xff' * 32 + material)


def x3dh_initiate(identity: Identity, ephemeral: X25519PrivateKey,
                   peer_identity_pub: bytes, peer_verify_pub: bytes,
                   peer_signed_prekey_pub: bytes, peer_signed_prekey_sig: bytes,
                   peer_one_time_prekey_pub: bytes | None) -> bytes:
    """Отправитель: получатель может быть офлайн, весь секрет считается из
    его заранее опубликованного бандла + нашего одноразового ephemeral-ключа.

    DH1 = DH(IK_self,  SPK_peer)
    DH2 = DH(EK_self,  IK_peer)
    DH3 = DH(EK_self,  SPK_peer)
    DH4 = DH(EK_self,  OPK_peer)   — если one-time prekey ещё был в запасе
    """
    if not verify_sig(peer_verify_pub, peer_signed_prekey_pub, peer_signed_prekey_sig):
        raise RatchetError('signed prekey signature does not verify')
    dh1 = _dh(identity.private_key, peer_signed_prekey_pub)
    dh2 = _dh(ephemeral, peer_identity_pub)
    dh3 = _dh(ephemeral, peer_signed_prekey_pub)
    material = dh1 + dh2 + dh3
    if peer_one_time_prekey_pub:
        material += _dh(ephemeral, peer_one_time_prekey_pub)
    return _x3dh_kdf(material)


def x3dh_respond(identity: Identity, signed_prekey_priv: X25519PrivateKey,
                  one_time_prekey_priv: X25519PrivateKey | None,
                  peer_identity_pub: bytes, peer_ephemeral_pub: bytes) -> bytes:
    """Получатель, при первом сообщении от отправителя: пересчитывает зеркально
    те же 3-4 DH (ECDH коммутативен для одной и той же пары ключей), получая
    ТОТ ЖЕ секрет, что и x3dh_initiate — без единого обмена в реальном времени."""
    dh1 = _dh(signed_prekey_priv, peer_identity_pub)
    dh2 = _dh(identity.private_key, peer_ephemeral_pub)
    dh3 = _dh(signed_prekey_priv, peer_ephemeral_pub)
    material = dh1 + dh2 + dh3
    if one_time_prekey_priv:
        material += _dh(one_time_prekey_priv, peer_ephemeral_pub)
    return _x3dh_kdf(material)


# ═══════════════════════════════════════════════════════════════════════
# Double Ratchet — ключ на каждое сообщение поверх секрета из X3DH
# ═══════════════════════════════════════════════════════════════════════

def _kdf_rk(root_key: bytes, dh_out: bytes) -> tuple[bytes, bytes]:
    """DH-ratchet шаг: (старый root key, новый DH-выход) → (новый root key,
    chain key для новой цепочки)."""
    out = HKDF(algorithm=SHA256(), length=64, salt=root_key,
               info=b'dns-messenger-ratchet-rk-v1').derive(dh_out)
    return out[:32], out[32:]


def _kdf_ck(chain_key: bytes) -> tuple[bytes, bytes]:
    """Симметричный ratchet шаг внутри одной цепочки: (chain key) →
    (следующий chain key, ключ ЭТОГО сообщения). HMAC, не HKDF — это KDF
    цепочки на одном входе, а не вывод общего секрета из ECDH."""
    next_ck = hmac.new(chain_key, b'\x02', 'sha256').digest()
    msg_key = hmac.new(chain_key, b'\x01', 'sha256').digest()
    return next_ck, msg_key


_HEADER_FMT = '>32sII'          # dh_pub(32) || pn(uint32 BE) || n(uint32 BE)
_HEADER_LEN = struct.calcsize(_HEADER_FMT)


def _pack_header(dh_pub: bytes, pn: int, n: int) -> bytes:
    return struct.pack(_HEADER_FMT, dh_pub, pn, n)


def _unpack_header(data: bytes) -> tuple[bytes, int, int]:
    return struct.unpack(_HEADER_FMT, data[:_HEADER_LEN])


class RatchetSession:
    """Double Ratchet-состояние для одной пары собеседников (один peer).

    Не потокобезопасен — как и остальные per-peer структуры UserMessenger
    (peer_keys, group_keys и т.п.), один экземпляр используется из одного
    потока за раз. Не персистентен (Phase 2 плана) — живёт в памяти процесса,
    рестарт сервера требует нового X3DH-хендшейка для этой пары."""

    def __init__(self):
        self.root_key: bytes = b''
        self.dhs: X25519PrivateKey | None = None   # своя текущая DH-ratchet пара
        self.dhs_pub: bytes = b''
        self.dhr: bytes | None = None              # публичный DH-ratchet ключ пира
        self.send_chain: bytes | None = None
        self.recv_chain: bytes | None = None
        self.send_n = 0
        self.recv_n = 0
        self.prev_chain_len = 0
        # (dhr_pub на момент вывода, n) → ключ сообщения — для того, что
        # придёт не по порядку или позже, чем следующий DH-ratchet шаг.
        self.skipped: dict[tuple[bytes, int], bytes] = {}

    @classmethod
    def init_initiator(cls, shared_secret: bytes, peer_signed_prekey_pub: bytes) -> 'RatchetSession':
        """Alice, сразу после x3dh_initiate. peer_signed_prekey_pub — signed
        prekey получателя, играет роль его «текущего» ratchet-ключа до самого
        первого настоящего DH-ratchet шага с его стороны."""
        s = cls()
        s.root_key = shared_secret
        s.dhs = generate_prekey_pair()
        s.dhs_pub = prekey_public_bytes(s.dhs)
        s.dhr = peer_signed_prekey_pub
        dh_out = _dh(s.dhs, s.dhr)
        s.root_key, s.send_chain = _kdf_rk(s.root_key, dh_out)
        return s

    @classmethod
    def init_responder(cls, shared_secret: bytes,
                        own_signed_prekey: X25519PrivateKey) -> 'RatchetSession':
        """Bob, сразу после x3dh_respond. Переиспользует свой signed prekey как
        первую DH-ratchet пару — Alice уже посчитала DH против его публичной
        половины (ровно то, что Bob опубликовал)."""
        s = cls()
        s.root_key = shared_secret
        s.dhs = own_signed_prekey
        s.dhs_pub = prekey_public_bytes(s.dhs)
        s.dhr = None
        return s

    def encrypt(self, plaintext: bytes) -> bytes:
        if self.send_chain is None:
            raise RatchetError('no sending chain established yet')
        self.send_chain, msg_key = _kdf_ck(self.send_chain)
        header = _pack_header(self.dhs_pub, self.prev_chain_len, self.send_n)
        self.send_n += 1
        return header + encrypt(plaintext, msg_key, aad=header)

    def _skip_recv(self, until: int):
        if self.recv_chain is None:
            return
        if until - self.recv_n > MAX_SKIPPED_KEYS:
            raise RatchetError('too many skipped messages — refusing to burn memory')
        while self.recv_n < until:
            self.recv_chain, msg_key = _kdf_ck(self.recv_chain)
            self.skipped[(self.dhr, self.recv_n)] = msg_key
            self.recv_n += 1
            if len(self.skipped) > MAX_SKIPPED_KEYS:
                # Отбрасываем самые старые — сообщение, пришедшее совсем
                # поздно, станет нечитаемым. Осознанный компромисс лимита,
                # не ошибка: dict сохраняет порядок вставки в Python 3.7+.
                del self.skipped[next(iter(self.skipped))]

    def _dh_ratchet_step(self, new_dhr_pub: bytes):
        self.prev_chain_len = self.send_n
        self.send_n = 0
        self.recv_n = 0
        self.dhr = new_dhr_pub
        dh_out = _dh(self.dhs, self.dhr)
        self.root_key, self.recv_chain = _kdf_rk(self.root_key, dh_out)
        self.dhs = generate_prekey_pair()
        self.dhs_pub = prekey_public_bytes(self.dhs)
        dh_out2 = _dh(self.dhs, self.dhr)
        self.root_key, self.send_chain = _kdf_rk(self.root_key, dh_out2)

    def decrypt(self, data: bytes) -> bytes:
        if len(data) < _HEADER_LEN:
            raise RatchetError('truncated ratchet message')
        header = data[:_HEADER_LEN]
        dh_pub, pn, n = _unpack_header(header)
        ct = data[_HEADER_LEN:]

        skip_key = self.skipped.pop((dh_pub, n), None)
        if skip_key is not None:
            return decrypt(ct, skip_key, aad=header)

        if self.dhr is None or dh_pub != self.dhr:
            # Новый ratchet-шаг от пира: сначала дораскрываем оставшиеся
            # ключи СТАРОЙ принимающей цепочки (pn сообщений могло ещё не
            # дойти), только потом переключаемся на новую.
            if self.recv_chain is not None:
                self._skip_recv(pn)
            self._dh_ratchet_step(dh_pub)

        self._skip_recv(n)
        self.recv_chain, msg_key = _kdf_ck(self.recv_chain)
        self.recv_n += 1
        return decrypt(ct, msg_key, aad=header)

    # ── Персистентность (Phase 2) ────────────────────────────────────────
    # Сериализация состояния целиком — то же самое, что держится в памяти,
    # просто в виде, который можно зашифровать и записать на диск. Ключ
    # шифрования — не наша забота (ratchet_storage_key ниже + web_client.py's
    # save_ratchet_state), эти методы имеют дело только с открытой формой.

    def to_dict(self) -> dict:
        def b64(x):
            return base64.b64encode(x).decode('ascii') if x is not None else None
        return {
            'root_key': b64(self.root_key),
            'dhs_priv': b64(prekey_private_bytes(self.dhs)) if self.dhs else None,
            'dhs_pub': b64(self.dhs_pub) if self.dhs_pub else None,
            'dhr': b64(self.dhr),
            'send_chain': b64(self.send_chain),
            'recv_chain': b64(self.recv_chain),
            'send_n': self.send_n,
            'recv_n': self.recv_n,
            'prev_chain_len': self.prev_chain_len,
            'skipped': [[b64(dh), n, b64(mk)] for (dh, n), mk in self.skipped.items()],
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'RatchetSession':
        def ub64(x):
            return base64.b64decode(x) if x is not None else None
        s = cls()
        s.root_key = ub64(data['root_key'])
        priv = ub64(data['dhs_priv'])
        s.dhs = prekey_from_private_bytes(priv) if priv else None
        s.dhs_pub = ub64(data['dhs_pub']) or b''
        s.dhr = ub64(data['dhr'])
        s.send_chain = ub64(data['send_chain'])
        s.recv_chain = ub64(data['recv_chain'])
        s.send_n = data['send_n']
        s.recv_n = data['recv_n']
        s.prev_chain_len = data['prev_chain_len']
        s.skipped = {(ub64(dh), n): ub64(mk) for dh, n, mk in data['skipped']}
        return s


def ratchet_storage_key(identity: Identity) -> bytes:
    """Ключ шифрования ratchet-состояния на диске — выводится из УЖЕ
    расшифрованных identity-ключей через HKDF, а не заново из пароля.

    Пароль нигде не хранится дольше момента, когда UserMessenger расшифровал
    identity.key/prekeys.key (см. web_client.py) — держать его в памяти ради
    последующей перезаписи ratchet-состояния после каждого сообщения означало
    бы новую, более широкую поверхность хранения пароля. HKDF от identity даёт
    тот же уровень защиты (кто способен расшифровать identity.key, способен
    вычислить и этот ключ) без лишнего секрета в памяти."""
    return HKDF(algorithm=SHA256(), length=32, salt=None,
                info=b'dns-messenger-ratchet-storage-v1').derive(identity.private_bytes())
