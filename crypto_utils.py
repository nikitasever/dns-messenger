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
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)

# Длины «сырых» ключей X25519/Ed25519 — оба по 32 байта.
KEY_LEN = 32
SIG_LEN = 64

# Заголовок зашифрованного identity-файла. Формат:
#   IDENTITY_MAGIC || salt(16) || ChaCha20-Poly1305(nonce||ct||tag).
# Зашифрован ключом, выведенным из пароля аккаунта через scrypt. Без magic —
# «сырой» файл (аноним/легаси), читается как раньше.
IDENTITY_MAGIC = b'IDENC1\n'
_SCRYPT_N = 2 ** 17      # ~128 МБ памяти — заметно дороже для офлайн-перебора пароля


class IdentityLocked(Exception):
    """identity-файл зашифрован, а верного пароля нет (не передан или неверен)."""


def _derive_identity_key(password: str, salt: bytes) -> bytes:
    """Пароль → 32-байтный ключ шифрования файла (scrypt, memory-hard)."""
    return Scrypt(salt=salt, length=32, n=_SCRYPT_N, r=8, p=1).derive(
        password.encode('utf-8'))


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

    def save(self, path: str, password: str | None = None):
        """Сохранить личность. С паролем — шифруем файл (scrypt + ChaCha20),
        без пароля — сырые байты (легаси-миграция; аноним теперь на диск
        вообще не пишется, см. UserMessenger persist_identity). chmod 600 в
        любом случае."""
        raw = self.private_bytes()
        if password:
            salt = os.urandom(16)
            blob = IDENTITY_MAGIC + salt + encrypt(raw, _derive_identity_key(password, salt))
        else:
            blob = raw
        # os.open с mode=0o600 задаёт права ПРИ СОЗДАНИИ файла атомарно — в
        # отличие от write_bytes()+chmod(), между которыми был бы короткий
        # интервал, когда новый файл лежит с правами по умолчанию (umask),
        # потенциально читаемыми другими локальными пользователями системы.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(blob)
        # Существующий файл (перезапись/миграция) мог быть создан раньше с
        # другими правами — подчищаем и в этом случае. На Windows/иных ФС
        # chmod может быть no-op — не критично (см. mode= выше как основную
        # защиту при первом создании).
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    @classmethod
    def from_raw(cls, raw: bytes) -> 'Identity':
        """Собрать Identity из «сырых» приватных байт (private_bytes()).
        Общая точка для load() и для любого другого места, куда сырые ключи
        приходят не с диска (например, восстановленные из кода recovery)."""
        x_priv = X25519PrivateKey.from_private_bytes(raw[:KEY_LEN])
        if len(raw) >= 2 * KEY_LEN:
            ed_priv = Ed25519PrivateKey.from_private_bytes(raw[KEY_LEN:2 * KEY_LEN])
            return cls(x_priv, ed_priv)
        # Старый файл только с X25519 — доращиваем Ed25519-ключом. Персист (в т.ч.
        # апгрейд формата и шифрование) делает вызывающий код, у которого есть
        # контекст пароля (UserMessenger.__init__).
        return cls(x_priv)

    @classmethod
    def load(cls, path: str, password: str | None = None) -> 'Identity':
        raw = Path(path).read_bytes()
        if raw.startswith(IDENTITY_MAGIC):
            if not password:
                raise IdentityLocked('identity is encrypted; a password is required')
            body = raw[len(IDENTITY_MAGIC):]
            salt, ct = body[:16], body[16:]
            try:
                raw = decrypt(ct, _derive_identity_key(password, salt))
            except Exception:
                raise IdentityLocked('wrong password for the identity file')
        return cls.from_raw(raw)

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


# ── Safety number (фаза 3, docs/ratchet-plan.md) ──────────────────────────
# Signal-style: по 30 байт итерированного самохеша на каждого собеседника
# (дороже подобрать бандл с заданным отпечатком, чем одиночным хешем),
# сведённые к 5-значным группам, отсортированные по имени пользователя так,
# чтобы оба собеседника получили ОДНУ И ТУ ЖЕ строку независимо от того, кто
# 'self', а кто 'peer'. Это не альтернатива TOFU-пиннингу (тот уже есть и
# ловит подмену бандла на лету) — это ручная сверка при первом контакте, до
# того как есть с чем сравнивать пин.
import hashlib as _hashlib

SAFETY_NUMBER_ROUNDS = 5200


def identity_fingerprint(username: str, bundle: bytes,
                          rounds: int = SAFETY_NUMBER_ROUNDS) -> bytes:
    data = _hashlib.sha512(username.encode('utf-8') + bundle).digest()
    for _ in range(rounds):
        data = _hashlib.sha512(data + bundle).digest()
    return data[:30]


def _fingerprint_digits(fp: bytes) -> str:
    """30 байт → 30 десятичных цифр, по 5 байт на 5-значную группу."""
    groups = []
    for i in range(0, 30, 5):
        n = int.from_bytes(fp[i:i + 5], 'big') % 100000
        groups.append(f'{n:05d}')
    return ''.join(groups)


def safety_number(user_a: str, bundle_a: bytes, user_b: str, bundle_b: bytes) -> str:
    """60-значный комбинированный отпечаток пары. Симметричен: порядок
    аргументов a/b не влияет на результат (сортировка по имени пользователя)."""
    pair = sorted([(user_a, bundle_a), (user_b, bundle_b)], key=lambda p: p[0])
    return ''.join(_fingerprint_digits(identity_fingerprint(u, b)) for u, b in pair)


def format_safety_number(digits: str) -> str:
    """60 цифр → 12 групп по 5, разделённых пробелом — как отображает Signal."""
    return ' '.join(digits[i:i + 5] for i in range(0, len(digits), 5))


# ── Аутентификация запросов к релею (регистрация / poll) ─────────────
# Релей — stateless DNS, «кто спрашивает» из транспорта не узнать. Клиент
# подписывает запрос своим Ed25519-ключом, релей проверяет против verify-ключа
# из зарегистрированного бандла. Отдельные контексты не дают переиспользовать
# подпись регистрации как подпись poll и наоборот.
POLL_SIG_CONTEXT = b'dnsmsg-poll-v1'
FPOLL_SIG_CONTEXT = b'dnsmsg-fpoll-v1'
REG_SIG_CONTEXT = b'dnsmsg-reg-v1'


def poll_signing_input(user: str, nonce: str, ts: str) -> bytes:
    """Канонические байты, которые клиент подписывает для poll-запроса (DM).

    ts (клиентская unix-метка времени, тоже подписана) даёт релею способ
    отклонить переигранный (nonce, sig) НЕЗАВИСИМО от seen_poll_nonces —
    тот живёт только в памяти и обнуляется рестартом релея."""
    return POLL_SIG_CONTEXT + b'|' + user.encode('utf-8') + b'|' + \
        nonce.encode('ascii') + b'|' + ts.encode('ascii')


def fpoll_signing_input(user: str, nonce: str, ts: str) -> bytes:
    """То же для опроса входящих файлов. Отдельный контекст не даёт выдать
    подпись DM-poll за подпись file-poll (и наоборот)."""
    return FPOLL_SIG_CONTEXT + b'|' + user.encode('utf-8') + b'|' + \
        nonce.encode('ascii') + b'|' + ts.encode('ascii')


GLIST_SIG_CONTEXT = b'dnsmsg-glist-v1'


def glist_signing_input(user: str, nonce: str, ts: str) -> bytes:
    """Подпись запроса списка групп: не даёт чужому перечислить членства user'а."""
    return GLIST_SIG_CONTEXT + b'|' + user.encode('utf-8') + b'|' + \
        nonce.encode('ascii') + b'|' + ts.encode('ascii')


def reg_signing_input(user: str, bundle: bytes) -> bytes:
    """Канонические байты подписи регистрации: доказывает владение бандлом."""
    return REG_SIG_CONTEXT + b'|' + user.encode('utf-8') + b'|' + bundle


GPOLL_SIG_CONTEXT = b'dnsmsg-gpoll-v1'
GINVITE_SIG_CONTEXT = b'dnsmsg-ginvite-v1'


def gpoll_signing_input(gid: str, user: str, nonce: str, ts: str) -> bytes:
    """Подпись опроса группового ящика: без неё релей принял бы ЛЮБОЕ заявленное
    имя как поллера — а раз group_mail отмечает сообщение прочитанным по имени
    из запроса, чужой мог бы отметить чужие сообщения прочитанными раньше
    настоящего получателя (кража доставки) или преждевременно выбить их из
    хранилища релея (msgs.pop при readers >= members)."""
    return GPOLL_SIG_CONTEXT + b'|' + gid.encode('utf-8') + b'|' + \
        user.encode('utf-8') + b'|' + nonce.encode('ascii') + b'|' + ts.encode('ascii')


def ginvite_signing_input(gid: str, inviter: str, invited: str) -> bytes:
    """Подпись приглашения в группу: без неё релей принял бы приглашение от
    ЛЮБОГО заявленного 'inviter' (проверяется лишь членство по имени, не
    владение ключом), позволяя чужому раздувать grp['members'] произвольными
    именами — что мешает вычитке (readers >= members никогда не достигается)
    и даёт постороннему статус «участник» для legit gpoll под тем же именем.

    Без nonce (в отличие от poll/glist): повтор ЭТОЙ подписи лишь заново
    исполняет то же самое приглашение того же inviter'а того же user'а в ту же
    группу — идемпотентно и безвредно, а бюджет DNS-имени (~253 симв.) не
    позволяет добавить ещё один лейбл сверх подписи и запечатанного ключа."""
    return GINVITE_SIG_CONTEXT + b'|' + gid.encode('utf-8') + b'|' + \
        inviter.encode('utf-8') + b'|' + invited.encode('utf-8')


GLEAVE_SIG_CONTEXT = b'dnsmsg-gleave-v1'
GKICK_SIG_CONTEXT = b'dnsmsg-gkick-v1'


def gleave_signing_input(gid: str, user: str, nonce: str, ts: str) -> bytes:
    """Подпись самостоятельного выхода из группы: без неё релей принял бы
    заявленный уход ЛЮБОГО имени — посторонний мог бы выкинуть чужого
    участника из группы, просто заявив 'я — он, я ухожу'. nonce+ts (как в
    gpoll/glist, не как в ginvite — здесь нет вложенного ключа, бюджет
    DNS-имени не поджимает) закрывают повтор: без них перехваченный уход
    можно было бы переиграть и после того, как участника пригласили обратно."""
    return GLEAVE_SIG_CONTEXT + b'|' + gid.encode('utf-8') + b'|' + \
        user.encode('utf-8') + b'|' + nonce.encode('ascii') + b'|' + ts.encode('ascii')


def gkick_signing_input(gid: str, kicker: str, target: str, nonce: str, ts: str) -> bytes:
    """Подпись исключения участника: тот же риск, что у gleave, только
    заявленный актёр — 'kicker', а не сама жертва. Умышленно не ограничено
    создателем группы — тот же ungated-модель доверия, что уже у ginvite
    (любой участник может пригласить, значит любой может и исключить)."""
    return GKICK_SIG_CONTEXT + b'|' + gid.encode('utf-8') + b'|' + \
        kicker.encode('utf-8') + b'|' + target.encode('utf-8') + b'|' + \
        nonce.encode('ascii') + b'|' + ts.encode('ascii')


GMEMBERS_SIG_CONTEXT = b'dnsmsg-gmembers-v1'


def gmembers_signing_input(gid: str, user: str, nonce: str, ts: str) -> bytes:
    """Подпись запроса списка участников группы: список — не публичная
    информация (кто состоит в чате), выдаётся только реально проверенному
    члену группы, не любому заявившему себя им."""
    return GMEMBERS_SIG_CONTEXT + b'|' + gid.encode('utf-8') + b'|' + \
        user.encode('utf-8') + b'|' + nonce.encode('ascii') + b'|' + ts.encode('ascii')


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

def encrypt(plaintext: bytes, key: bytes, aad: bytes | None = None) -> bytes:
    """ChaCha20-Poly1305: → nonce(12) || ciphertext || tag(16).

    aad (authenticated but not encrypted) is None by default — every existing
    caller keeps behaving exactly as before. The ratchet module passes the
    message header here so a tampered header fails the AEAD tag instead of
    silently steering decryption toward the wrong derived key."""
    nonce = os.urandom(12)
    return nonce + ChaCha20Poly1305(key).encrypt(nonce, plaintext, aad)


def decrypt(data: bytes, key: bytes, aad: bytes | None = None) -> bytes:
    """ChaCha20-Poly1305: nonce(12) || ciphertext || tag(16) → plaintext."""
    return ChaCha20Poly1305(key).decrypt(data[:12], data[12:], aad)


# ── Групповые ключи ─────────────────────────────────────────────────

def generate_group_key() -> bytes:
    """Случайный 32-байт ключ для группового чата."""
    return os.urandom(32)


def seal_group_key(group_key: bytes, my_identity: Identity, peer_public: bytes,
                    gid: str) -> bytes:
    """Шифрует групповой ключ для конкретного участника (ECDH + ChaCha20).

    gid — обязательные associated data. ECDH-секрет зависит только от пары
    identity-ключей, а НЕ от группы, поэтому без привязки к gid недоверенный
    релей мог бы переиграть перехваченный шифротекст ключа одной группы как
    «ключ» другой группы между теми же двумя людьми (cross-group replay)."""
    shared = my_identity.derive_shared_key(peer_public)
    nonce = os.urandom(12)
    ct = ChaCha20Poly1305(shared).encrypt(nonce, group_key, gid.encode('utf-8'))
    return nonce + ct


def unseal_group_key(sealed: bytes, my_identity: Identity, sender_public: bytes,
                      gid: str) -> bytes:
    """Расшифровывает групповой ключ, полученный от создателя/инвайтера."""
    shared = my_identity.derive_shared_key(sender_public)
    return ChaCha20Poly1305(shared).decrypt(sealed[:12], sealed[12:], gid.encode('utf-8'))


GKEY_SIG_CONTEXT = b'dnsmsg-gkey-v1'


def gkey_signing_input(gid: str, group_key: bytes, invited: str) -> bytes:
    """Подпись инвайтера над (group, ключ, приглашённый). ECDH-шифрование уже
    доказывает, что блок расшифровал именно тот, кто владеет приватным ключом
    заявленного отправителя, но подпись даёт явное, проверяемое подтверждение,
    что ИМЕННО ЭТОТ создатель/инвайтер авторизовал раздачу ИМЕННО ЭТОГО ключа
    ИМЕННО ЭТОМУ участнику — второй, независимый слой защиты от релея,
    подменяющего инвайтера в неаутентифицированном ginvite (см. G3)."""
    return GKEY_SIG_CONTEXT + b'|' + gid.encode('utf-8') + b'|' + group_key + b'|' + invited.encode('utf-8')
