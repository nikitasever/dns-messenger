"""
Веб-клиент DNS Messenger — Flask + SocketIO.
Многопользовательский: каждый браузер/вкладка — свой юзер.

Запуск:
    python web_client.py --server 127.0.0.1 --port 15353
    # Откройте http://localhost:8080 — логин через браузер.
    # Вторая вкладка → другой ник → второй пользователь.
"""

import os
import shutil
import threading
import time
import json
import random
import hashlib
import secrets
import base64
import io
import ipaddress
import re
from pathlib import Path

from flask import (
    Flask, render_template, request, jsonify, session,
    send_file as flask_send_file, Response,
)
from flask_socketio import SocketIO, emit, join_room
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

import webauthn
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria, UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
)
from webauthn.helpers.exceptions import WebAuthnException

import webpush
from transport import UDPTransport, DoHTransport, MultiTransport
from protocol import (
    CMD_REGISTER, CMD_GETKEY, CMD_SEND, CMD_POLL,
    CMD_GROUP_CREATE, CMD_GROUP_INVITE, CMD_GROUP_SEND,
    CMD_GROUP_POLL, CMD_GROUP_LIST, CMD_GROUP_LEAVE, CMD_GROUP_KICK,
    CMD_GROUP_MEMBERS,
    CMD_FILE_HEADER, CMD_FILE_CHUNK, CMD_FILE_POLL, CMD_FILE_DOWNLOAD,
    CMD_LIST_USERS,
    MAX_LABEL_LEN, MAX_DOMAIN_LEN, NONCE_OVERHEAD,
    b32encode, b32decode, chunk_string, gen_msg_id, gen_nonce,
)
from crypto_utils import (
    Identity, IdentityLocked, IDENTITY_MAGIC, KEY_LEN, encrypt, decrypt,
    generate_group_key, seal_group_key, unseal_group_key,
    split_bundle, build_signed, open_signed,
    poll_signing_input, fpoll_signing_input, glist_signing_input,
    reg_signing_input, gpoll_signing_input, ginvite_signing_input,
    gleave_signing_input, gkick_signing_input, gmembers_signing_input,
    _derive_identity_key, safety_number, format_safety_number,
)
from ratchet import (
    RatchetSession, RatchetError,
    generate_prekey_pair, prekey_public_bytes, prekey_private_bytes,
    prekey_from_private_bytes, sign_prekey, x3dh_initiate, x3dh_respond,
    ratchet_storage_key,
)

app = Flask(__name__)
# SECRET_KEY: the env var wins. Failing that, generate a random key once and
# persist it, rather than either hardcoding a fallback or regenerating per run.
# A fixed string in the source would let anyone forge session cookies offline;
# regenerating silently logged every user out on each restart, while the UI
# still looked signed in and only the API returned "Not authorized".
SECRET_FILE = Path('.messenger_secret')


def _load_or_create_secret() -> str:
    env = os.environ.get('SECRET_KEY')
    if env:
        return env
    try:
        existing = SECRET_FILE.read_text('utf-8').strip()
        if len(existing) >= 32:
            return existing
    except OSError:
        pass
    key = secrets.token_hex(32)
    try:
        SECRET_FILE.write_text(key, 'utf-8')
        try:
            os.chmod(SECRET_FILE, 0o600)
        except OSError:
            pass          # Windows/иные ФС — не критично
        print(f'[+] Session key generated: {SECRET_FILE} (set SECRET_KEY to override)')
    except OSError as e:
        print(f'[!] Could not persist the session key ({e}); sessions will not '
              f'survive a restart. Set the SECRET_KEY env var.')
    return key


app.config['SECRET_KEY'] = _load_or_create_secret()

# Harden session cookie: HttpOnly (default), SameSite=Lax (blocks cross-site
# sends on top-level navigations/CSRF while still allowing normal same-site
# use), and Secure when served over HTTPS (opt-in via env since local/dev
# deployments are often plain HTTP and Secure would break the cookie there).
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', '0') == '1'
# Жёсткий предел размера тела запроса: Werkzeug оборвёт запрос ещё на разборе,
# ДО буферизации. Без него api_file_send делал f.read() всего тела в память до
# проверки 512 КБ — прямой memory/disk DoS многогигабайтной загрузкой. 2 МБ с
# запасом покрывает 512-КБ файл + data-URL фото профиля + multipart-обвязку.
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

# За обратным прокси (HTTPS-терминация на Caddy/nginx) реальный IP и схема
# приходят в X-Forwarded-*. Включаем доверие к ним ТОЛЬКО по TRUST_PROXY=1 —
# иначе при прямом доступе клиент мог бы подделать свой IP заголовком и обойти
# rate-limit. Один хоп прокси. remote_addr после этого = настоящий IP клиента.
if os.environ.get('TRUST_PROXY', '0') == '1':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

socketio = SocketIO(app, cors_allowed_origins='*', manage_session=False)


# ═══════════════════════════════════════════════════════════════════════
# CSRF-защита (synchronizer token, привязанный к сессии)
# ═══════════════════════════════════════════════════════════════════════
# SameSite=Lax уже отсекает большинство cross-site POST, но это defense-in-depth:
# каждой сессии выдаётся токен, он рендерится в <meta> на страницу, а клиентский
# csrf.js добавляет его в заголовок X-CSRF-Token на всех мутирующих fetch'ах.
# Сервер сверяет заголовок с токеном сессии и отклоняет несовпадения.
CSRF_SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS', 'TRACE'}


@app.before_request
def _csrf_protect():
    # Токен нужен любой сессии (даже до логина — форма входа тоже шлёт POST).
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
        session.permanent = False
    if request.method in CSRF_SAFE_METHODS:
        return
    # Socket.IO — свой транспорт/handshake, same-origin, не навигируемая форма;
    # мутаций стойкого состояния там нет (только сигналинг звонков/typing).
    if request.path.startswith('/socket.io'):
        return
    # Под TESTING проверку выключаем (как Flask-WTF): существующие тесты шлют
    # POST без токена. Отдельный tests/test_csrf.py гоняет её с TESTING=False.
    if app.config.get('TESTING'):
        return
    token = request.headers.get('X-CSRF-Token', '')
    if not (token and secrets.compare_digest(token, session.get('csrf', ''))):
        return jsonify({'ok': False, 'error': 'CSRF token missing or invalid'}), 403


@app.context_processor
def _inject_csrf():
    # Делает {{ csrf_token }} доступным во всех шаблонах для <meta>-тега.
    return {'csrf_token': session.get('csrf', '')}


# ═══════════════════════════════════════════════════════════════════════
# Пароли и хранение аккаунтов
# ═══════════════════════════════════════════════════════════════════════

ACCOUNTS_FILE = Path('.messenger_accounts.json')
# Only base64-encoded raster images — no room for a bare "," after the MIME
# type (which is how the profile-photo XSS smuggled `" onerror="..."` past a
# startswith('data:image/') check) and no SVG (which can carry <script>/event
# handlers of its own even though <img> mostly neuters SVG script execution).
PHOTO_DATA_URL_RE = re.compile(
    r'^data:image/(png|jpe?g|gif|webp);base64,[A-Za-z0-9+/]+=*$')

ADMIN_FILE = Path('.messenger_admin.json')
BLOCKED_FILE = Path('.messenger_blocked.json')


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text('utf-8'))
        except Exception:
            pass
    return {}


def _save_json(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), 'utf-8')
    # Здесь лежат хэши паролей аккаунтов и админа — не мировая читаемость.
    # На Windows/иных ФС chmod может быть no-op, это не критично.
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _hash_password(password: str, salt: str = '') -> tuple[str, str]:
    """Хэшировать пароль с солью. Возвращает (hash, salt)."""
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode(), 100_000)
    return h.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    h, _ = _hash_password(password, salt)
    return secrets.compare_digest(h, stored_hash)


def get_accounts() -> dict:
    return _load_json(ACCOUNTS_FILE)


def save_account(username: str, password_hash: str, salt: str):
    accs = get_accounts()
    accs[username] = {'hash': password_hash, 'salt': salt}
    _save_json(ACCOUNTS_FILE, accs)


WEBAUTHN_FILE = Path('.messenger_webauthn.json')
webauthn_lock = threading.Lock()
# Второй фактор — только для register/login (пароль есть), не для анонима.
# Сколько живёт подписанный клиентом challenge и «прошёл пароль, жду
# passkey»-тикет: оба короткие и одноразовые (challenge стирается сразу
# после использования; pending-тикет — по истечении PENDING_2FA_TTL).
WEBAUTHN_CHALLENGE_TTL = 120.0
PENDING_2FA_TTL = 180.0


def get_webauthn_creds() -> dict:
    with webauthn_lock:
        return _load_json(WEBAUTHN_FILE)


def user_webauthn_creds(username: str) -> list:
    return get_webauthn_creds().get(username, [])


def save_webauthn_cred(username: str, cred_id_b64: str, public_key_b64: str,
                        sign_count: int, label: str):
    with webauthn_lock:
        data = _load_json(WEBAUTHN_FILE)
        creds = data.setdefault(username, [])
        creds.append({
            'id': cred_id_b64, 'public_key': public_key_b64,
            'sign_count': sign_count, 'label': label[:60],
            'added_ts': time.time(),
        })
        _save_json(WEBAUTHN_FILE, data)


def update_webauthn_sign_count(username: str, cred_id_b64: str, sign_count: int):
    with webauthn_lock:
        data = _load_json(WEBAUTHN_FILE)
        for c in data.get(username, []):
            if c['id'] == cred_id_b64:
                c['sign_count'] = sign_count
                break
        _save_json(WEBAUTHN_FILE, data)


def remove_webauthn_cred(username: str, cred_id_b64: str) -> bool:
    with webauthn_lock:
        data = _load_json(WEBAUTHN_FILE)
        creds = data.get(username, [])
        remaining = [c for c in creds if c['id'] != cred_id_b64]
        if len(remaining) == len(creds):
            return False
        data[username] = remaining
        _save_json(WEBAUTHN_FILE, data)
        return True


BACKUP_CODES_FILE = Path('.messenger_backup_codes.json')
# Без 0/O/1/I/L — на глаз не спутать при переписывании с экрана на бумагу.
BACKUP_CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
BACKUP_CODE_COUNT = 10


def _normalize_backup_code(code: str) -> str:
    return re.sub(r'[\s-]', '', code.strip().upper())


def _gen_backup_code() -> str:
    raw = ''.join(secrets.choice(BACKUP_CODE_ALPHABET) for _ in range(10))
    return raw  # хранится/сверяется без разделителя; дефис только для показа


def generate_backup_codes(username: str) -> list[str]:
    """Генерирует НОВЫЙ комплект кодов, безвозвратно затирая старый — старые
    коды, даже неиспользованные, после этого не сработают. Возвращает коды
    в открытом виде РОВНО ОДИН РАЗ (вызывающий должен показать их и не
    сохранять текст ответа); на диск попадают только их хэши."""
    codes = [_gen_backup_code() for _ in range(BACKUP_CODE_COUNT)]
    with webauthn_lock:
        data = _load_json(BACKUP_CODES_FILE)
        entries = []
        for code in codes:
            h, s = _hash_password(code)
            entries.append({'hash': h, 'salt': s, 'used': False})
        data[username] = entries
        _save_json(BACKUP_CODES_FILE, data)
    return [f'{c[:5]}-{c[5:]}' for c in codes]


def backup_codes_status(username: str) -> tuple[int, int]:
    """(осталось_неиспользованных, всего_в_последнем_комплекте)."""
    with webauthn_lock:
        entries = _load_json(BACKUP_CODES_FILE).get(username, [])
    remaining = sum(1 for e in entries if not e['used'])
    return remaining, len(entries)


def consume_backup_code(username: str, code: str) -> bool:
    """Одноразовая проверка: код должен совпасть с ХЭШЕМ неиспользованной
    записи. При успехе помечает её использованной необратимо (перебор
    ограничен rate_limited() на вызывающей стороне — как и для пароля)."""
    normalized = _normalize_backup_code(code)
    if not normalized:
        return False
    with webauthn_lock:
        data = _load_json(BACKUP_CODES_FILE)
        entries = data.get(username, [])
        for e in entries:
            if e['used']:
                continue
            if _verify_password(normalized, e['hash'], e['salt']):
                e['used'] = True
                _save_json(BACKUP_CODES_FILE, data)
                return True
        return False


# ── Account recovery (пароль забыт целиком) ─────────────────────────────
# Пароль аккаунта — это ещё и ключ шифрования identity-файла (см.
# UserMessenger.__init__), поэтому backup-коды 2FA тут не годятся: они лишь
# ПОДТВЕРЖДАЮТ личность после уже введённого пароля, а не расшифровывают
# ничего. Код восстановления обязан САМ БЫТЬ ключом: это второй scrypt-wrap
# тех же сырых приватных байт (identity.private_bytes()), под ключом,
# выведенным из recovery-кода тем же способом (_derive_identity_key), и
# хранится рядом с identity.key как identity.recovery. Сервер никогда не
# хранит сам код — только шифротекст; поэтому проверка «код верный?» — это
# попытка расшифровать, а не сравнение с хэшем.
RECOVERY_CODE_LEN = 24  # 24 симв. из 31-буквенного алфавита ≈ 119 бит энтропии


def _recovery_file(username: str) -> Path:
    return Path(f'.messenger_{username}') / 'identity.recovery'


def _gen_recovery_code() -> str:
    return ''.join(secrets.choice(BACKUP_CODE_ALPHABET) for _ in range(RECOVERY_CODE_LEN))


def _format_recovery_code(code: str) -> str:
    return '-'.join(code[i:i + 4] for i in range(0, len(code), 4))


def has_recovery_code(username: str) -> bool:
    return _recovery_file(username).exists()


def generate_recovery_code(username: str, identity: Identity) -> str:
    """Генерирует НОВЫЙ код восстановления, безвозвратно затирая старый —
    старый код (даже неиспользованный) после этого расшифровать identity
    больше не сможет. Возвращает код в открытом виде РОВНО ОДИН РАЗ; на диск
    попадает только шифротекст сырых ключей под ним."""
    code = _gen_recovery_code()
    salt = os.urandom(16)
    raw = identity.private_bytes()
    blob = salt + encrypt(raw, _derive_identity_key(code, salt))
    path = _recovery_file(username)
    path.parent.mkdir(exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(blob)
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass
    return _format_recovery_code(code)


def purge_username_data(username: str):
    """Стирает ВСЕ данные, привязанные к нику: identity.key, код
    восстановления, TOFU-пины (весь .messenger_<user>/), passkeys, backup-коды
    и фото профиля. Без этого удалённый ник нельзя безопасно отдать заново —
    новый человек с тем же ником унаследовал бы чужой зашифрованный identity
    (и не смог бы вообще зарегистрироваться: UserMessenger пытался бы
    расшифровать ЧУЖОЙ identity.key своим новым паролем и падал с
    IdentityLocked) или, того хуже, старый passkey/recovery-код продолжал бы
    формально числиться на этот ник."""
    shutil.rmtree(f'.messenger_{username}', ignore_errors=True)
    with webauthn_lock:
        wa = _load_json(WEBAUTHN_FILE)
        if wa.pop(username, None) is not None:
            _save_json(WEBAUTHN_FILE, wa)
        bc = _load_json(BACKUP_CODES_FILE)
        if bc.pop(username, None) is not None:
            _save_json(BACKUP_CODES_FILE, bc)
    profiles = get_profiles()
    if profiles.pop(username, None) is not None:
        _save_json(PROFILES_FILE, profiles)


def consume_recovery_code(username: str, code: str) -> Identity | None:
    """Пробует расшифровать сохранённые сырые ключи кодом восстановления.
    Успех/неудача видны только по тому, расшифровалось ли — сам код нигде
    не хранится, сравнивать не с чем."""
    normalized = re.sub(r'[\s-]', '', code.strip().upper())
    if not normalized:
        return None
    path = _recovery_file(username)
    if not path.exists():
        return None
    try:
        blob = path.read_bytes()
        salt, ct = blob[:16], blob[16:]
        raw = decrypt(ct, _derive_identity_key(normalized, salt))
        return Identity.from_raw(raw)
    except Exception:
        return None


def webauthn_rp():
    """(rp_id, origin) для текущего запроса. rp_id обязан быть доменом БЕЗ
    порта и совпадать между регистрацией и логином passkey — иначе браузер
    откажет в церемонии (WebAuthn это проверяет сам)."""
    return request.host.split(':')[0], request.url_root.rstrip('/')


def pending_2fa_user() -> str | None:
    """Имя пользователя, который только что верно ввёл пароль и теперь должен
    подтвердить passkey, или None. Тикет одноразовый по смыслу (сессия его не
    выдаёт заново без нового /api/login) и короткоживущий."""
    user = session.get('pending_2fa_user')
    exp = session.get('pending_2fa_exp', 0)
    if not user or time.time() > exp:
        session.pop('pending_2fa_user', None)
        session.pop('pending_2fa_exp', None)
        return None
    return user


def get_blocked() -> set:
    data = _load_json(BLOCKED_FILE)
    return set(data.get('blocked', []))


def save_blocked(blocked: set):
    _save_json(BLOCKED_FILE, {'blocked': list(blocked)})


def get_json_dict() -> dict:
    """Safely pull a JSON object body from the request.

    request.json (or .get_json()) happily returns whatever the client sent —
    a list, a string, a number, None — and calling .get() on anything but a
    dict raises AttributeError, which Flask turns into an unhandled 500. All
    routes should go through this helper instead of touching request.json
    directly so a malformed body (e.g. a JSON array) degrades to an empty
    dict/validation error instead of crashing the server.
    """
    try:
        d = request.get_json(silent=True, force=False)
    except Exception:
        d = None
    return d if isinstance(d, dict) else {}


# ── Per-user session revocation ─────────────────────────────────────────
# Regular (non-admin) session cookies are stateless/signed, so without this
# a captured pre-logout cookie would remain valid forever, even after the
# legitimate user explicitly logs out. Mirror the admin 'sv' (session
# version) approach: each login stamps the session with the user's current
# version, and logout bumps the version so any previously issued cookie for
# that account (forged or genuine) is rejected on the next request.
#
# The versions must outlive the process. They used to be memory-only, which
# was masked by SECRET_KEY being regenerated per run (that invalidated every
# cookie anyway). Now that the key is persisted, resetting the versions on
# restart would resurrect exactly the pre-logout cookies this is meant to kill.
SV_FILE = Path('.messenger_sv.json')
_user_sv_lock = threading.Lock()


def _read_sv() -> dict:
    data = _load_json(SV_FILE)
    return {k: int(v) for k, v in data.items() if isinstance(v, (int, str)) and str(v).isdigit()}


_user_sv: dict[str, int] = _read_sv()


def current_user_sv(username: str) -> int:
    with _user_sv_lock:
        return _user_sv.get(username, 0)


def bump_user_sv(username: str) -> int:
    with _user_sv_lock:
        _user_sv[username] = _user_sv.get(username, 0) + 1
        try:
            _save_json(SV_FILE, _user_sv)
        except OSError as e:
            # Не удалось записать — отзыв в этом процессе всё равно действует.
            print(f'[!] Could not persist session revocation for {username}: {e}')
        return _user_sv[username]


def is_admin_session() -> bool:
    """Check the session against the admin's current session-version.

    Session cookies are stateless/signed, so a plain `session['is_admin']`
    flag remains valid forever (even after logout) as long as the cookie is
    replayed. To make logout actually revoke access, the admin record keeps
    a 'sv' (session version) counter; each login stamps the session with the
    current version, and logout bumps the version so any previously issued
    cookie (forged or genuine) is rejected on the next request.
    """
    if not session.get('is_admin'):
        return False
    admin_data = _load_json(ADMIN_FILE)
    current_sv = admin_data.get('sv', 0)
    return session.get('sv') == current_sv


# ── Simple in-memory rate limiting ──────────────────────────────────────
_rate_limit_lock = threading.Lock()
_rate_limit_hits: dict[str, list[float]] = {}
_rate_limit_last_sweep = 0.0
_RATE_LIMIT_SWEEP_INTERVAL = 300.0


def rate_limited(key: str, max_attempts: int = 5, window_seconds: float = 60.0) -> bool:
    """Return True if `key` has exceeded max_attempts within window_seconds."""
    now = time.time()
    with _rate_limit_lock:
        # Ключ здесь — IP клиента. Списки внутри чистятся, но сами ключи иначе
        # накапливались бы вечно: атакующий с ротацией IP (тривиально по IPv6)
        # раздул бы словарь. Периодически выметаем ключи, у которых все отметки
        # уже протухли.
        global _rate_limit_last_sweep
        if now - _rate_limit_last_sweep > _RATE_LIMIT_SWEEP_INTERVAL:
            _rate_limit_last_sweep = now
            for k in list(_rate_limit_hits):
                fresh = [t for t in _rate_limit_hits[k] if now - t < window_seconds]
                if fresh:
                    _rate_limit_hits[k] = fresh
                else:
                    del _rate_limit_hits[k]
        hits = _rate_limit_hits.setdefault(key, [])
        hits[:] = [t for t in hits if now - t < window_seconds]
        if len(hits) >= max_attempts:
            return True
        hits.append(now)
        return False


# Per-ACCOUNT login-failure throttle. The per-IP limit is defeated by IP
# rotation (IPv6/proxy pool), so a named account also needs its own counter.
# Keyed by username; only real (registered) accounts are ever recorded (login
# rejects unknown names first), so this dict is bounded by the user count.
_login_failures: dict[str, list[float]] = {}
ACCOUNT_FAIL_WINDOW = 900.0     # 15 минут
ACCOUNT_FAIL_MAX = 20           # неудач за окно, потом временно блокируем


def account_throttled(username: str) -> bool:
    now = time.time()
    with _rate_limit_lock:
        hits = [t for t in _login_failures.get(username, []) if now - t < ACCOUNT_FAIL_WINDOW]
        _login_failures[username] = hits
        return len(hits) >= ACCOUNT_FAIL_MAX


def note_login_failure(username: str):
    now = time.time()
    with _rate_limit_lock:
        hits = [t for t in _login_failures.get(username, []) if now - t < ACCOUNT_FAIL_WINDOW]
        hits.append(now)
        _login_failures[username] = hits


def client_ip() -> str:
    return request.remote_addr or 'unknown'


def init_admin():
    """Создать файл админа если его нет."""
    if not ADMIN_FILE.exists():
        # No known/predictable default password — generate a random one so
        # nobody can log in as admin out-of-the-box without ever seeing it.
        password = secrets.token_urlsafe(12)
        h, s = _hash_password(password)
        _save_json(ADMIN_FILE, {'hash': h, 'salt': s, 'change_required': True, 'sv': 0})
        print(f'[!] Generated admin password: {password} (change it at /admin — this is shown only once)')


# ═══════════════════════════════════════════════════════════════════════
# Мессенджер (один инстанс на пользователя)
# ═══════════════════════════════════════════════════════════════════════

# Повтор отправки чанка при потере UDP-пакета. На DoH таймауты редки (там свой
# TLS-ретрай), так что это в основном для прямого UDP-пути.
SEND_RETRIES = 3
SEND_RETRY_BACKOFF = 0.15   # секунды, растёт линейно с номером попытки


def _is_transient_err(res: str) -> bool:
    """Ошибка похожа на потерю пакета (повтор осмыслен), а не на отказ сервера."""
    return res.startswith('ERR') and any(
        s in res for s in ('timeout', 'no_response', 'no_transport'))


# ═══════════════════════════════════════════════════════════════════════
# Prekeys для X3DH (docs/ratchet-plan.md, фаза 1) — только для личных чатов
# зарегистрированных аккаунтов. Анонимный режим (никакого персистентного
# пароля/identity) остаётся на легаси-статической ECDH-схеме, см. send_dm.
#
# Приватная половина (signed prekey + пул one-time prekeys) хранится в
# .messenger_<user>/prekeys.key, зашифрованная паролем аккаунта той же схемой,
# что и identity.key (scrypt + ChaCha20-Poly1305) — переиспользуем
# _derive_identity_key, не изобретаем новый формат.
#
# Публичные бандлы (то, что рассылается желающим написать этому пользователю)
# лежат открытым текстом в PREKEY_FILE — как и профили/webauthn-креды, это не
# секрет, секрет — только приватные половины.
#
# ВАЖНО: пароль нигде не хранится дольше момента логина (см. Identity.load) —
# поэтому prekeys.key может быть (пере)записан ТОЛЬКО в UserMessenger.__init__
# (там, где пароль ещё жив), а не из отдельного authenticated-эндпоинта уже
# после логина. Публикация/пополнение пула — часть __init__, отдельного
# /api/prekeys/publish не нужно; сам X3DH-обмен бандлами — внутренняя
# серверная бухгалтерия между send_dm/_decrypt_from и PREKEY_FILE, браузеру
# тут вообще нечего вызывать напрямую.
PREKEY_FILE = Path('.messenger_prekeys.json')
prekey_lock = threading.Lock()
ONE_TIME_PREKEY_POOL_TARGET = 50
ONE_TIME_PREKEY_REPLENISH_THRESHOLD = 10
SIGNED_PREKEY_ROTATE_AFTER = 7 * 86400.0   # 7 дней
PREKEY_MAGIC = b'PKENC1\n'

RATCHET_SCHEME_LEGACY_STATIC = 0    # старая статическая ECDH — аноним и фолбэк
RATCHET_SCHEME_RATCHET_INIT = 1     # первое сообщение сессии: несёт X3DH-данные
RATCHET_SCHEME_RATCHET_CONT = 2     # продолжение уже установленной ratchet-сессии


def _pack_ratchet_init(ephemeral_pub: bytes, one_time_pub: bytes | None, ratchet_ct: bytes) -> bytes:
    """scheme(1) || ephemeral_pub(32) || has_otpk(1) || otpk_pub(32, нули если
    has_otpk=0) || ratchet_ct. otpk_pub всегда занимает те же 32 байта —
    отдельный флаг has_otpk честнее, чем «все нули = отсутствует» (валидный
    X25519-ключ технически МОГ бы совпасть с нулями, пусть и с исчезающей
    вероятностью)."""
    has_otpk = one_time_pub is not None
    otpk_field = one_time_pub if has_otpk else (b'\x00' * KEY_LEN)
    return (bytes([RATCHET_SCHEME_RATCHET_INIT]) + ephemeral_pub
            + bytes([1 if has_otpk else 0]) + otpk_field + ratchet_ct)


def _unpack_ratchet_init(body: bytes) -> tuple[bytes, bytes | None, bytes]:
    ephemeral_pub = body[:KEY_LEN]
    has_otpk = body[KEY_LEN] == 1
    otpk_pub = body[KEY_LEN + 1: KEY_LEN + 1 + KEY_LEN] if has_otpk else None
    ratchet_ct = body[KEY_LEN + 1 + KEY_LEN:]
    return ephemeral_pub, otpk_pub, ratchet_ct


def _pack_ratchet_continue(ratchet_ct: bytes) -> bytes:
    return bytes([RATCHET_SCHEME_RATCHET_CONT]) + ratchet_ct


def _prekey_priv_file(username: str) -> Path:
    return Path(f'.messenger_{username}') / 'prekeys.key'


def save_prekey_store(username: str, password: str, store: dict):
    """store: {'signed_priv': X25519PrivateKey, 'signed_pub': bytes,
    'signed_sig': bytes, 'signed_ts': float, 'one_time': {pub: priv}}."""
    payload = json.dumps({
        'signed_priv': base64.b64encode(prekey_private_bytes(store['signed_priv'])).decode(),
        'signed_pub': base64.b64encode(store['signed_pub']).decode(),
        'signed_sig': base64.b64encode(store['signed_sig']).decode(),
        'signed_ts': store['signed_ts'],
        'one_time': {
            base64.b64encode(pub).decode(): base64.b64encode(prekey_private_bytes(priv)).decode()
            for pub, priv in store['one_time'].items()
        },
    }).encode('utf-8')
    salt = os.urandom(16)
    blob = PREKEY_MAGIC + salt + encrypt(payload, _derive_identity_key(password, salt))
    path = _prekey_priv_file(username)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(blob)
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass


def load_prekey_store(username: str, password: str) -> dict | None:
    path = _prekey_priv_file(username)
    if not path.exists():
        return None
    raw = path.read_bytes()
    if not raw.startswith(PREKEY_MAGIC):
        return None
    body = raw[len(PREKEY_MAGIC):]
    salt, ct = body[:16], body[16:]
    try:
        payload = json.loads(decrypt(ct, _derive_identity_key(password, salt)))
    except Exception:
        return None
    return {
        'signed_priv': prekey_from_private_bytes(base64.b64decode(payload['signed_priv'])),
        'signed_pub': base64.b64decode(payload['signed_pub']),
        'signed_sig': base64.b64decode(payload['signed_sig']),
        'signed_ts': payload['signed_ts'],
        'one_time': {
            base64.b64decode(pub_b64): prekey_from_private_bytes(base64.b64decode(priv_b64))
            for pub_b64, priv_b64 in payload['one_time'].items()
        },
    }


def bootstrap_or_replenish_prekeys(identity: Identity, existing: dict | None,
                                    now: float | None = None) -> tuple[dict, bool]:
    """Возвращает (store, changed). Создаёт signed prekey с нуля, если его ещё
    нет; ротирует его, если он старше SIGNED_PREKEY_ROTATE_AFTER; доливает
    one-time prekeys до целевого размера, если пул просел ниже порога.
    changed=False, только если всё уже было в порядке — тогда вызывающему не
    нужно ничего дописывать на диск/публиковать заново.

    Известная граница ротации: уже начатый, но ещё не долетевший до нас
    X3DH-хендшейк, использующий ИМЕННО СТАРЫЙ signed prekey, после ротации
    декодируется в неверный секрет — сообщение не расшифруется (безопасный,
    явный отказ, не молчаливая порча), просто придётся отправить заново. Мы
    сознательно не держим предыдущий signed prekey «ещё валидным» (как
    рекомендует избегать этого сам Signal-протокол при желании упростить
    реализацию) — окно (недели между ротациями против секунд на долёт
    сообщения через DNS-туннель) делает эту границу крайне маловероятной на
    практике."""
    now = now if now is not None else time.time()
    if existing is None:
        signed_priv = generate_prekey_pair()
        signed_pub = prekey_public_bytes(signed_priv)
        store = {
            'signed_priv': signed_priv,
            'signed_pub': signed_pub,
            'signed_sig': sign_prekey(identity, signed_pub),
            'signed_ts': now,
            'one_time': {},
        }
        changed = True
    else:
        store = existing
        changed = False
        if now - store['signed_ts'] > SIGNED_PREKEY_ROTATE_AFTER:
            signed_priv = generate_prekey_pair()
            signed_pub = prekey_public_bytes(signed_priv)
            store['signed_priv'] = signed_priv
            store['signed_pub'] = signed_pub
            store['signed_sig'] = sign_prekey(identity, signed_pub)
            store['signed_ts'] = now
            changed = True
    if len(store['one_time']) < ONE_TIME_PREKEY_REPLENISH_THRESHOLD:
        to_add = ONE_TIME_PREKEY_POOL_TARGET - len(store['one_time'])
        for _ in range(max(to_add, 0)):
            otk = generate_prekey_pair()
            store['one_time'][prekey_public_bytes(otk)] = otk
        changed = True
    return store, changed


def get_prekey_bundles() -> dict:
    return _load_json(PREKEY_FILE)


def publish_prekey_bundle(username: str, store: dict):
    """Публикует/обновляет публичную часть бандла. Не трогает one-time
    prekeys, которые уже были опубликованы и ещё не разобраны — только
    добавляет новые (см. bootstrap_or_replenish_prekeys), поэтому re-publish
    не аннулирует уже выданные, но ещё не потреблённые one-time ключи."""
    with prekey_lock:
        data = get_prekey_bundles()
        already_public = set()
        if username in data:
            already_public = {base64.b64decode(p) for p in data[username].get('one_time', [])}
        all_pub = set(store['one_time'].keys()) | already_public
        data[username] = {
            'signed_pub': base64.b64encode(store['signed_pub']).decode(),
            'signed_sig': base64.b64encode(store['signed_sig']).decode(),
            'signed_ts': store['signed_ts'],
            'one_time': [base64.b64encode(p).decode() for p in all_pub],
        }
        _save_json(PREKEY_FILE, data)


def take_prekey_bundle(username: str) -> dict | None:
    """Отдаёт публичный бандл получателя и АТОМАРНО забирает (удаляет из
    пула) один one-time prekey, если он ещё был в запасе — иначе отдаёт
    бандл без него (X3DH проходит и так, просто без DH4-компоненты)."""
    with prekey_lock:
        data = get_prekey_bundles()
        entry = data.get(username)
        if not entry:
            return None
        one_time_pub = None
        if entry['one_time']:
            one_time_pub = entry['one_time'].pop(0)
            _save_json(PREKEY_FILE, data)
        return {
            'signed_pub': base64.b64decode(entry['signed_pub']),
            'signed_sig': base64.b64decode(entry['signed_sig']),
            'one_time_pub': base64.b64decode(one_time_pub) if one_time_pub else None,
        }


# ── Персистентность ratchet-состояния (docs/ratchet-plan.md, фаза 2) ────
# Один файл на пару собеседников — .messenger_<user>/ratchet_<peer>.state,
# зашифрован ключом из ratchet_storage_key() (выведен из УЖЕ расшифрованной
# identity, не из пароля напрямую — см. докстринг ratchet_storage_key).
# Загружается целиком в UserMessenger.__init__, дозаписывается после каждого
# encrypt/decrypt через send_dm/_decrypt_from — так рестарт сервера (у вас
# частые деплои) больше не рвёт активные секретные переписки.

def _ratchet_state_file(username: str, peer: str) -> Path:
    return Path(f'.messenger_{username}') / f'ratchet_{peer}.state'


def save_ratchet_state(username: str, peer: str, storage_key: bytes, session: RatchetSession):
    payload = json.dumps(session.to_dict()).encode('utf-8')
    blob = encrypt(payload, storage_key)
    path = _ratchet_state_file(username, peer)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(blob)
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass


def load_ratchet_state(username: str, peer: str, storage_key: bytes) -> RatchetSession | None:
    path = _ratchet_state_file(username, peer)
    if not path.exists():
        return None
    try:
        payload = decrypt(path.read_bytes(), storage_key)
        return RatchetSession.from_dict(json.loads(payload))
    except Exception:
        # Испорченный/чужой файл (или сменился storage_key, чего в норме не
        # бывает) — не роняем логин, просто эта сессия начнётся с нуля через
        # X3DH при следующем сообщении, как если бы файла не было вовсе.
        return None


def load_all_ratchet_states(username: str, storage_key: bytes) -> dict[str, 'RatchetSession']:
    data_dir = Path(f'.messenger_{username}')
    result = {}
    if not data_dir.exists():
        return result
    for f in data_dir.glob('ratchet_*.state'):
        peer = f.stem[len('ratchet_'):]
        session = load_ratchet_state(username, peer, storage_key)
        if session is not None:
            result[peer] = session
    return result


class UserMessenger:
    def __init__(self, username: str, transport, password: str | None = None,
                 persist_identity: bool = True):
        self.username = username
        self.transport = transport
        self.running = False
        self.poll_errors = 0
        self.persist_identity = persist_identity

        # Анонимный режим (persist_identity=False): identity и пины держим
        # ТОЛЬКО в памяти этого объекта, не читаем и не пишем на диск. Анонимный
        # identity-файл не защищён паролем — если бы он лежал по пути,
        # производному лишь от НИКА, любой, кто позже выберет тот же ник
        # (случайно или намеренно, спустя произвольное время после рестарта),
        # тихо загрузил бы личность/почтовый ящик/пины ПРЕДЫДУЩЕГО анонима под
        # этим ником — полный захват identity без единой проверки пароля.
        if not persist_identity:
            self.identity = Identity()
            self.peer_keys: dict[str, bytes] = {}
            self.peer_verify: dict[str, bytes] = {}
            self.group_keys: dict[str, bytes] = {}
            self.groups: dict[str, dict] = {}
            self._group_key_applied: dict[str, str] = {}
            self._group_last_members: dict[str, set] = {}
            self._pins_file = None
            self._pins: dict[str, str] = {}
            self.key_alerts: set[str] = set()
            # Аноним не персистит пароль/identity — значит и prekeys/ratchet
            # (X3DH требует identity, подписывающий signed prekey, устойчивую
            # между сессиями) для него не имеют смысла. Личные сообщения с/от
            # анонима остаются на легаси-статической ECDH-схеме (см. send_dm).
            self.prekeys = None
            self.ratchets: dict[str, RatchetSession] = {}
            self._ratchet_key = None
            return

        data_dir = Path(f'.messenger_{username}')
        data_dir.mkdir(exist_ok=True)
        key_file = data_dir / 'identity.key'
        # Личность зарегистрированного пользователя шифруется паролем аккаунта.
        # Если файл зашифрован, а пароля нет (напр. авто-восстановление сессии
        # после рестарта) — load бросит IdentityLocked, и вызывающий отправит
        # пользователя на логин.
        existing = key_file.read_bytes() if key_file.exists() else b''
        if existing:
            self.identity = Identity.load(str(key_file), password)
        else:
            self.identity = Identity()
        was_encrypted = existing.startswith(IDENTITY_MAGIC)
        plain_len = 0 if was_encrypted else len(existing)
        # Пишем файл, если: он новый; легаси-файл только с X25519 (доращиваем
        # Ed25519); или у нас есть пароль, а файл ещё не зашифрован (миграция).
        if (not existing
                or (not was_encrypted and plain_len < 2 * KEY_LEN)
                or (password and not was_encrypted)):
            self.identity.save(str(key_file), password)

        self.peer_keys: dict[str, bytes] = {}      # user → X25519 (для ECDH)
        self.peer_verify: dict[str, bytes] = {}    # user → Ed25519 (для подписи)
        self.group_keys: dict[str, bytes] = {}
        self.groups: dict[str, dict] = {}
        self._group_key_applied: dict[str, str] = {}
        self._group_last_members: dict[str, set] = {}

        # TOFU-пиннинг: бандл ключей пира, увиденный при первом контакте.
        # Если сервер позже отдаёт другой ключ под тем же именем — это подмена
        # (подмена при регистрации / MITM), и мы её не принимаем молча.
        self._pins_file = data_dir / 'pins.json'
        self._pins: dict[str, str] = _load_json(self._pins_file)  # user → bundle_b32
        self.key_alerts: set[str] = set()          # пиры со сменившимся ключом

        # Prekeys для X3DH (docs/ratchet-plan.md) — переиспользуем/пополняем
        # тут же, а не из отдельного эндпоинта: пароль дальше нигде не хранится
        # (см. Identity.load), поэтому re-encrypt prekeys.key возможен ТОЛЬКО
        # здесь, пока он ещё жив.
        self.prekeys = None
        if password:
            existing_prekeys = load_prekey_store(username, password)
            store, changed = bootstrap_or_replenish_prekeys(self.identity, existing_prekeys)
            self.prekeys = store
            if changed:
                save_prekey_store(username, password, store)
            publish_prekey_bundle(username, store)

        # Ratchet-состояние (docs/ratchet-plan.md, фаза 2) — ключ шифрования
        # выводится из уже расшифрованной identity (не из пароля напрямую),
        # поэтому доступен всё время жизни объекта и переживает то, что пароль
        # нигде дальше не хранится. Существующие сессии подхватываются с диска
        # сразу тут — рестарт сервера их больше не рвёт.
        self._ratchet_key = ratchet_storage_key(self.identity) if self.prekeys else None
        self.ratchets: dict[str, RatchetSession] = (
            load_all_ratchet_states(username, self._ratchet_key) if self._ratchet_key else {}
        )

    def _q(self, labels):
        return self.transport.query(labels)

    def _q_reliable(self, labels):
        """Запрос с повтором при потере пакета (транзиентная ошибка).

        Безопасно только для ИДЕМПОТЕНТНЫХ операций:
          • записи: сборка чанков/файла на сервере идемпотентна по id;
          • чистые чтения без побочек: getkey, скачивание чанка файла.
        НЕЛЬЗЯ для поллов (p/q/t) — сервер снимает сообщение из ящика до ответа,
        и повтор вытащил бы уже следующее (или потерял текущее).
        """
        res = self._q(labels)
        tries = 0
        while tries < SEND_RETRIES and _is_transient_err(res):
            tries += 1
            time.sleep(SEND_RETRY_BACKOFF * tries)
            res = self._q(labels)
        return res

    def register(self) -> bool:
        # Подписываем регистрацию своим Ed25519-ключом: релей закрепляет имя за
        # этим ключом (TOFR) и потом не даёт чужому переписать/опрашивать его.
        # Формат нагрузки: bundle_b32 + sig_b32 (оба по 64 байта → режется по длине).
        bundle = self.identity.public_bundle()
        sig = self.identity.sign(reg_signing_input(self.username, bundle))
        payload = b32encode(bundle) + b32encode(sig)
        # Идемпотентно (тот же ключ) — можно повторять при потере пакета.
        return self._q_reliable(
            [CMD_REGISTER, self.username] + chunk_string(payload, MAX_LABEL_LEN)
        ).startswith('OK')

    def _remember_peer(self, user: str, bundle: bytes) -> bytes | None:
        """Пиннит бандл пира по TOFU. Возвращает доверенный X25519 или None,
        если ключ сменился относительно закреплённого (подмена)."""
        b32 = b32encode(bundle)
        pinned = self._pins.get(user)
        if pinned is None:
            self._pins[user] = b32
            if self._pins_file is not None:
                try:
                    _save_json(self._pins_file, self._pins)
                except OSError:
                    pass
            self.key_alerts.discard(user)
        elif pinned != b32:
            # Ключ под этим именем изменился — держимся закреплённого.
            self.key_alerts.add(user)
            bundle = b32decode(pinned)
        else:
            self.key_alerts.discard(user)
        x, ed = split_bundle(bundle)
        self.peer_keys[user] = x
        if ed:
            self.peer_verify[user] = ed
        return x

    def get_peer_key(self, user: str) -> bytes | None:
        if user in self.peer_keys:
            return self.peer_keys[user]
        res = self._q_reliable([CMD_GETKEY, user])   # чтение, повтор безопасно
        if res.startswith('KEY:'):
            flag_str, _, bundle_b32 = res[4:].partition(':')
            if flag_str not in ('0', '1'):
                return None                      # неожиданный формат — не падаем
            try:
                bundle = b32decode(bundle_b32)
            except Exception:
                return None                      # битый base32 от релея — не падаем
            # Принимаем только валидные длины бандла: 32 (легаси X25519) или 64
            # (X25519+Ed25519). Отбрасывает мусор и странные усечения.
            if len(bundle) not in (KEY_LEN, 2 * KEY_LEN):
                return None
            # pinned=1 по построению сервера означает 64-байтный бандл (см.
            # _h_register): 32 байта при pinned=1 — противоречивый ответ,
            # похожий на релей, тайком урезающий чужой бандл до "легаси" и тем
            # понижающий Ed25519-проверку до вечного 'unverified'/'unknown'.
            if flag_str == '1' and len(bundle) != 2 * KEY_LEN:
                return None
            return self._remember_peer(user, bundle)
        return None

    def peer_verify_key(self, user: str) -> bytes | None:
        if user not in self.peer_verify and user not in self.peer_keys:
            self.get_peer_key(user)   # подтягивает и пиннит бандл
        return self.peer_verify.get(user)

    def _persist_ratchet(self, peer: str, session: RatchetSession):
        """Дозаписывает ratchet-состояние на диск после КАЖДОГО encrypt/decrypt
        (не батчем раз в N сообщений) — если бы состояние отставало от того,
        что реально ушло/пришло, рестарт между записями откатывал бы сессию
        к устаревшей точке, а не терял бы её целиком: пропущенные ключи
        цепочки за это время это переживут (skipped-key механизм на то и
        сделан), но проще и надёжнее вообще не создавать это окно."""
        if self._ratchet_key is not None:
            save_ratchet_state(self.username, peer, self._ratchet_key, session)

    def send_dm(self, to_user: str, text: str) -> dict:
        pk = self.get_peer_key(to_user)
        if not pk:
            return {'ok': False, 'error': f'User "{to_user}" not online. Must sign in first.'}
        ctx = self.username.encode('utf-8') + b'\x00' + to_user.encode('utf-8')
        signed = build_signed(self.identity, ctx, text.encode('utf-8'))

        # Double Ratchet, если у нас самих есть prekeys (не аноним) и уже
        # установлена сессия с этим пиром, ИЛИ мы можем её сейчас установить
        # (у пира есть опубликованный бандл). Иначе — легаси-статическая
        # ECDH-схема ниже, без forward secrecy (docs/ratchet-plan.md фаза 1:
        # ratchet покрывает только пары, где ОБЕ стороны его поддерживают).
        session = self.ratchets.get(to_user)
        if session is None and self.prekeys is not None:
            bundle = take_prekey_bundle(to_user)
            peer_verify = self.peer_verify.get(to_user)
            if bundle is not None and peer_verify is not None:
                try:
                    ephemeral = generate_prekey_pair()
                    shared_secret = x3dh_initiate(
                        self.identity, ephemeral,
                        peer_identity_pub=pk, peer_verify_pub=peer_verify,
                        peer_signed_prekey_pub=bundle['signed_pub'],
                        peer_signed_prekey_sig=bundle['signed_sig'],
                        peer_one_time_prekey_pub=bundle['one_time_pub'],
                    )
                    session = RatchetSession.init_initiator(shared_secret, bundle['signed_pub'])
                    ratchet_ct = session.encrypt(signed)
                    ct = _pack_ratchet_init(prekey_public_bytes(ephemeral),
                                             bundle['one_time_pub'], ratchet_ct)
                    self.ratchets[to_user] = session
                    self._persist_ratchet(to_user, session)
                    ok = self._send_chunked(CMD_SEND, [to_user, self.username], ct)
                    return {'ok': ok, 'error': '' if ok else 'Send error'}
                except RatchetError:
                    pass   # бандл/подпись оказались нерабочими — откат ниже

        if session is not None:
            ratchet_ct = session.encrypt(signed)
            self._persist_ratchet(to_user, session)
            ct = _pack_ratchet_continue(ratchet_ct)
            ok = self._send_chunked(CMD_SEND, [to_user, self.username], ct)
            return {'ok': ok, 'error': '' if ok else 'Send error'}

        shared = self.identity.derive_shared_key(pk)
        ct = bytes([RATCHET_SCHEME_LEGACY_STATIC]) + encrypt(signed, shared)
        ok = self._send_chunked(CMD_SEND, [to_user, self.username], ct)
        return {'ok': ok, 'error': '' if ok else 'Send error'}

    def poll_dm(self) -> list[dict]:
        msgs = []
        while True:
            # Подписываем каждый poll свежим nonce: релей проверяет подпись
            # против нашего закреплённого ключа и не даёт чужому опустошить ящик.
            nonce = gen_nonce()
            ts = str(int(time.time()))
            sig = self.identity.sign(poll_signing_input(self.username, nonce, ts))
            res = self._q([CMD_POLL, self.username, nonce, ts]
                          + chunk_string(b32encode(sig), MAX_LABEL_LEN))
            if res == 'EMPTY' or res.startswith('ERR'):
                break
            if res.startswith('MSG:'):
                colon = res.index(':', 4)
                fr, data = res[4:colon], res[colon + 1:]
                text, auth = self._decrypt_from(fr, data)
                msgs.append({'type': 'dm', 'from': fr, 'text': text, 'auth': auth})
        return msgs

    def create_group(self, gid: str) -> bool:
        if self._q([CMD_GROUP_CREATE, gid, self.username]).startswith('OK'):
            self.group_keys[gid] = generate_group_key()
            return True
        return False

    def invite_to_group(self, gid: str, user: str) -> dict:
        pk = self.get_peer_key(user)
        if not pk:
            return {'ok': False, 'error': f'User "{user}" not found. Must sign in first.'}
        gk = self.group_keys.get(gid)
        if not gk:
            return {'ok': False, 'error': 'No group key'}
        # gid — associated data при шифровании (см. seal_group_key): ECDH-секрет
        # тот же для любой пары людей независимо от группы, поэтому без этого
        # ciphertext одной группы решифровался бы (успешно!) как ключ другой.
        sealed = seal_group_key(gk, self.identity, pk, gid)
        # Подпись поверх самого relay-запроса (gid, inviter, invited, nonce) —
        # доказывает релею, что ИМЕННО Я, владелец закреплённого имени
        # self.username, сейчас приглашаю user в gid. Без неё релей принял бы
        # invite от кого угодно, заявившего чужое имя инвайтера, и раздул
        # grp['members'] произвольными именами (см. crypto_utils.ginvite_signing_input).
        # DNS qname ограничен ~253 символами — бюджета хватает на один такой
        # сигнатурный блок сверх sealed-ключа, поэтому вторую (per-key) подпись
        # не добавляем: успешная AEAD-расшифровка с этим gid как AAD уже сама
        # по себе доказывает, что sealed создан владельцем заявленного
        # приватного ключа именно для этой группы — независимая подпись
        # добавила бы только избыточность, а не новую гарантию.
        invite_sig = self.identity.sign(
            ginvite_signing_input(gid, self.username, user))
        labels = [CMD_GROUP_INVITE, gid, self.username, user] + chunk_string(
            b32encode(invite_sig) + b32encode(sealed), MAX_LABEL_LEN)
        ok = self._q(labels).startswith('OK')
        return {'ok': ok, 'error': '' if ok else 'Error'}

    def send_group(self, gid: str, text: str) -> bool:
        gk = self.group_keys.get(gid)
        if not gk:
            return False
        # Подпись обязательна именно в группе: общий ключ расшифровывает всё,
        # и без подписи любой участник может выдать себя за другого.
        ctx = self.username.encode('utf-8') + b'\x00' + gid.encode('utf-8')
        signed = build_signed(self.identity, ctx, text.encode('utf-8'))
        return self._send_chunked(CMD_GROUP_SEND, [gid, self.username], encrypt(signed, gk))

    def poll_group(self, gid: str) -> list[dict]:
        msgs = []
        while True:
            # Подписываем poll: без этого чужой мог бы отметить наши групповые
            # сообщения прочитанными за нас (кража доставки) под нашим именем.
            nonce = gen_nonce()
            ts = str(int(time.time()))
            sig = self.identity.sign(gpoll_signing_input(gid, self.username, nonce, ts))
            res = self._q([CMD_GROUP_POLL, gid, self.username, nonce, ts]
                          + chunk_string(b32encode(sig), MAX_LABEL_LEN))
            if res == 'EMPTY' or res.startswith('ERR'):
                break
            if res.startswith('GMSG:'):
                colon = res.index(':', 5)
                fr, data = res[5:colon], res[colon + 1:]
                if fr == self.username:
                    continue
                gk = self.group_keys.get(gid)
                if gk:
                    try:
                        plain = decrypt(b32decode(data), gk)
                        ctx = fr.encode('utf-8') + b'\x00' + gid.encode('utf-8')
                        pt, auth = open_signed(plain, self.peer_verify_key(fr), ctx)
                        text = pt.decode('utf-8')
                        # В группе ключ общий, поэтому ПОДЛИННЫЙ отправитель всегда
                        # подписывает. Любой статус кроме 'verified' — подделка
                        # участником (в т.ч. 'unsigned'/'unverified', которые иначе
                        # рендерились бы без предупреждения). Жёстко метим 'forged'.
                        if auth != 'verified':
                            auth = 'forged'
                        if fr in self.key_alerts:
                            auth = 'key_changed'
                    except Exception as e:
                        text, auth = f'[error: {e}]', 'error'
                else:
                    text, auth = '[no key]', 'error'
                msgs.append({'type': 'group', 'group': gid, 'from': fr, 'text': text, 'auth': auth})
        return msgs

    def fetch_groups(self):
        # Подписываем запрос списка групп — чужой не перечислит наши членства.
        nonce = gen_nonce()
        ts = str(int(time.time()))
        sig = self.identity.sign(glist_signing_input(self.username, nonce, ts))
        res = self._q([CMD_GROUP_LIST, self.username, nonce, ts]
                      + chunk_string(b32encode(sig), MAX_LABEL_LEN))
        if not res.startswith('GROUPS:'):
            return
        for entry in res[7:].split('|'):
            parts = entry.split(':', 2)
            if len(parts) < 3:
                continue
            gid, key_from, key_data = parts
            # Фаза 4 (docs/ratchet-plan.md): key_data меняется не только при
            # первом инвайте, но и при ре-кее после kick/leave (см.
            # rekey_group) — переприменяем, только когда блок РЕАЛЬНО сменился
            # относительно того, что мы уже применили, а не всякий раз, когда
            # gid уже известен (старая проверка `gid in self.group_keys`
            # намертво игнорировала бы любой присланный позже ре-кей).
            if not key_data or not key_from or self._group_key_applied.get(gid) == key_data:
                continue
            spk = self.get_peer_key(key_from)
            if spk:
                try:
                    # unseal_group_key проверяет gid как AEAD-associated-data:
                    # ciphertext ключа ОДНОЙ группы больше не расшифруется как
                    # ключ ДРУГОЙ группы между теми же двумя identity, даже
                    # если релей подсунет его под другим gid (см. seal_group_key).
                    self.group_keys[gid] = unseal_group_key(
                        b32decode(key_data), self.identity, spk, gid)
                    self._group_key_applied[gid] = key_data
                except Exception:
                    pass

    def list_group_members(self, gid: str) -> list[str]:
        nonce = gen_nonce()
        ts = str(int(time.time()))
        sig = self.identity.sign(gmembers_signing_input(gid, self.username, nonce, ts))
        res = self._q([CMD_GROUP_MEMBERS, gid, self.username, nonce, ts]
                      + chunk_string(b32encode(sig), MAX_LABEL_LEN))
        if not res.startswith('MEMBERS:'):
            return []
        return [u for u in res[8:].split(',') if u]

    def leave_group(self, gid: str) -> bool:
        nonce = gen_nonce()
        ts = str(int(time.time()))
        sig = self.identity.sign(gleave_signing_input(gid, self.username, nonce, ts))
        ok = self._q([CMD_GROUP_LEAVE, gid, self.username, nonce, ts]
                     + chunk_string(b32encode(sig), MAX_LABEL_LEN)).startswith('OK')
        if ok:
            self.group_keys.pop(gid, None)
            self._group_key_applied.pop(gid, None)
            self._group_last_members.pop(gid, None)
        return ok

    def rekey_group(self, gid: str) -> dict:
        """Новый групповой ключ + рассылка остальным (фаза 4, docs/ratchet-plan.md).
        Переиспользует invite_to_group/ginvite как канал доставки — 'повторный
        инвайт' уже состоящему участнику для релея не отличим от обновления
        его ключа (grp['members'].add — идемпотентно, grp['keys'][user]
        перезаписывается). Кто ушёл/выкинут, тот НЕ входит в members и
        рассылку не получает — только это и даёт forward secrecy на leave/kick,
        а не сама по себе смена ключа."""
        members = self.list_group_members(gid)
        if self.username not in members:
            return {'ok': False, 'error': 'not a member'}
        new_key = generate_group_key()
        self.group_keys[gid] = new_key
        self._group_last_members[gid] = set(members)
        failed = []
        for user in members:
            if user == self.username:
                continue
            if not self.invite_to_group(gid, user).get('ok'):
                failed.append(user)
        return {'ok': True, 'failed': failed}

    def kick_member(self, gid: str, target: str) -> dict:
        nonce = gen_nonce()
        ts = str(int(time.time()))
        sig = self.identity.sign(gkick_signing_input(gid, self.username, target, nonce, ts))
        res = self._q([CMD_GROUP_KICK, gid, self.username, target, nonce, ts]
                      + chunk_string(b32encode(sig), MAX_LABEL_LEN))
        if not res.startswith('OK'):
            return {'ok': False, 'error': res}
        rekey = self.rekey_group(gid)
        return {'ok': True, 'rekey_failed': rekey.get('failed', [])}

    def check_group_rekey(self):
        """Децентрализованный ре-кей на добровольный leave (kick уже
        ре-кеит сам себя синхронно в kick_member — эта проверка нужна ТОЛЬКО
        для случая, когда участник ушёл сам, и никто не вызвал rekey_group
        явно). Вызывается из фонового поллинга для каждой известной группы.

        Без единого «админа» ждать, что кто-то один возьмёт на себя ре-кей,
        не на что — вместо debounce-таймера (как в референсе, см. отчёт по
        репозиторию друга) детерминированный выбор: ре-кеит только участник с
        лексикографически наименьшим именем среди ОСТАВШИХСЯ — ровно один
        кандидат на раунд, гонки между несколькими одновременными ре-кеями
        не бывает в принципе, а не гасится постфактум таймером."""
        for gid in list(self.group_keys):
            try:
                members = self.list_group_members(gid)
            except Exception:
                continue
            if not members or self.username not in members:
                continue
            prev = self._group_last_members.get(gid)
            self._group_last_members[gid] = set(members)
            if prev is None:
                continue     # первое наблюдение — не с чем сравнивать
            if set(members) < prev and self.username == min(members):
                self.rekey_group(gid)

    def send_file(self, to_user: str, filename: str, data: bytes) -> dict:
        pk = self.get_peer_key(to_user)
        if not pk:
            return {'ok': False, 'error': f'"{to_user}" not found'}
        shared = self.identity.derive_shared_key(pk)
        ct = encrypt(data, shared)
        fid = gen_msg_id()
        ct_b32 = b32encode(ct)

        overhead = len(f'f.{fid}.000.') + len(self.transport.domain) + 2 + NONCE_OVERHEAD
        avail = MAX_DOMAIN_LEN - overhead
        per_chunk = max(MAX_LABEL_LEN, (avail // (MAX_LABEL_LEN + 1)) * MAX_LABEL_LEN)
        chunks = chunk_string(ct_b32, per_chunk) if ct_b32 else ['']
        total = len(chunks)

        # Имя файла тоже E2E-шифруем тем же общим ключом — иначе релей видит
        # открытым текстом, как называется файл (само по себе может быть
        # чувствительным). Получатель расшифрует при опросе.
        name_b32 = b32encode(encrypt(filename.encode('utf-8'), shared))
        if self._q_reliable([CMD_FILE_HEADER, to_user, self.username, fid, name_b32, str(len(ct)), str(total)]).startswith('ERR'):
            return {'ok': False, 'error': 'Header error'}
        for seq, chunk in enumerate(chunks):
            if self._q_reliable([CMD_FILE_CHUNK, fid, str(seq)] + chunk_string(chunk, MAX_LABEL_LEN)).startswith('ERR'):
                return {'ok': False, 'error': f'Chunk error {seq}'}
        return {'ok': True, 'fid': fid}

    def poll_files(self) -> list[dict]:
        files = []
        while True:
            # Подписываем опрос входящих файлов (свой контекст, отличный от DM),
            # чтобы закреплённый file_inbox нельзя было опустошить чужому.
            nonce = gen_nonce()
            ts = str(int(time.time()))
            sig = self.identity.sign(fpoll_signing_input(self.username, nonce, ts))
            res = self._q([CMD_FILE_POLL, self.username, nonce, ts]
                          + chunk_string(b32encode(sig), MAX_LABEL_LEN))
            if res == 'EMPTY' or res.startswith('ERR'):
                break
            if res.startswith('FILE:'):
                parts = res[5:].split(':', 3)
                if len(parts) == 4:
                    fid, fr, name_b32, size = parts
                    fname = self._decrypt_filename(fr, name_b32)
                    files.append({'fid': fid, 'from': fr, 'name': fname, 'size': int(size)})
        return files

    def _decrypt_filename(self, sender: str, name_b32: str) -> str:
        """Расшифровать имя файла общим ключом с отправителем. Fallback на
        открытый текст — для файлов от старых клиентов (до E2E-имён)."""
        try:
            raw = b32decode(name_b32)
        except Exception:
            return 'unknown'
        pk = self.get_peer_key(sender)
        if pk:
            try:
                return decrypt(raw, self.identity.derive_shared_key(pk)).decode('utf-8')
            except Exception:
                pass  # не расшифровалось — вероятно, легаси-плейнтекст
        try:
            return raw.decode('utf-8')
        except Exception:
            return 'unknown'

    def download_file(self, fid: str, sender: str) -> bytes | None:
        # Докачиваемое скачивание: каждый чанк тянется через _q_reliable (повтор
        # при потере пакета), уже полученное сохраняется — потеря одного чанка
        # не рвёт всю загрузку. Чтение x.<fid>.<seq> идемпотентно, повтор
        # безопасен. При жёсткой ошибке возвращаем None, а не обрезанный файл.
        all_data, seq = '', 0
        while True:
            res = self._q_reliable([CMD_FILE_DOWNLOAD, fid, str(seq)])
            if res == 'EOF':
                break
            if not res.startswith('FDATA:'):
                return None                      # ERR (в т.ч. после ретраев) — не отдаём огрызок
            parts = res[6:].split(':', 2)
            if len(parts) != 3:
                return None
            all_data += parts[2]
            seq += 1
            if seq >= int(parts[1]):
                break
        if not all_data:
            return None
        pk = self.get_peer_key(sender)
        if not pk:
            return None
        try:
            return decrypt(b32decode(all_data), self.identity.derive_shared_key(pk))
        except Exception:
            return None

    def list_users(self) -> list[str]:
        res = self._q([CMD_LIST_USERS])
        if res.startswith('USERS:'):
            return res[6:].split('|')
        return []

    def _send_chunked(self, cmd, prefix, ct):
        data_b32 = b32encode(ct)
        mid = gen_msg_id()
        overhead = '.'.join([cmd] + prefix + [mid, '00', '00', ''])
        avail = MAX_DOMAIN_LEN - len(overhead) - len(self.transport.domain) - 2 - NONCE_OVERHEAD
        per_q = max(MAX_LABEL_LEN, (avail // (MAX_LABEL_LEN + 1)) * MAX_LABEL_LEN)
        chunks = chunk_string(data_b32, per_q) if data_b32 else ['']
        total = len(chunks)
        for seq, chunk in enumerate(chunks):
            labels = [cmd] + prefix + [mid, str(seq), str(total)] + chunk_string(chunk, MAX_LABEL_LEN)
            if self._q_reliable(labels).startswith('ERR'):
                return False
        return True

    def _decrypt_from(self, sender, data_b32):
        """→ (text, auth). auth: verified | forged | unverified | unsigned |
        key_changed | error."""
        try:
            raw = b32decode(data_b32)
            if not raw:
                return '[empty message]', 'error'
            scheme, body = raw[0], raw[1:]

            if scheme == RATCHET_SCHEME_LEGACY_STATIC:
                pk = self.get_peer_key(sender)
                if not pk:
                    return '[key not found]', 'error'
                plain = decrypt(body, self.identity.derive_shared_key(pk))

            elif scheme == RATCHET_SCHEME_RATCHET_CONT:
                # Ratchet-расшифровка сама по себе не требует X25519-ключа
                # пира (сессия уже несёт всё нужное), но open_signed() ниже
                # требует его Ed25519 verify-ключ для проверки подписи — а
                # peer_verify живёт только в памяти этого объекта, не
                # персистентно. На свежевосстановленном объекте (рестарт) он
                # пуст, даже если ratchet-сессия сама успешно подхватилась с
                # диска — без этого вызова подпись молча не проверялась бы
                # ('unverified' вместо 'verified') на первом же сообщении
                # после рестарта.
                self.peer_verify_key(sender)
                session = self.ratchets.get(sender)
                if session is None:
                    # Ratchet-состояние теперь персистентно (docs/ratchet-plan.md
                    # фаза 2) и подхватывается с диска в __init__, так что сюда
                    # мы попадаем не из-за обычного рестарта, а если файл
                    # состояния реально потерян/испорчен, либо пир прислал
                    # RATCHET_CONT без валидной сессии (протокольная ошибка/
                    # чужой шум) — расшифровывать нечем в любом случае.
                    return ('[ratchet session lost — ask them to send a new '
                            'message to restart the secure session]', 'error')
                plain = session.decrypt(body)
                self._persist_ratchet(sender, session)

            elif scheme == RATCHET_SCHEME_RATCHET_INIT:
                if self.prekeys is None:
                    return '[no prekeys available to complete the handshake]', 'error'
                pk = self.get_peer_key(sender)   # тянет и пиннит identity/verify-ключ
                if not pk:
                    return '[key not found]', 'error'
                ephemeral_pub, otpk_pub, ratchet_ct = _unpack_ratchet_init(body)
                otpk_priv = self.prekeys['one_time'].pop(otpk_pub, None) if otpk_pub else None
                shared_secret = x3dh_respond(
                    self.identity, self.prekeys['signed_priv'], otpk_priv,
                    peer_identity_pub=pk, peer_ephemeral_pub=ephemeral_pub,
                )
                session = RatchetSession.init_responder(shared_secret, self.prekeys['signed_priv'])
                plain = session.decrypt(ratchet_ct)
                self.ratchets[sender] = session
                self._persist_ratchet(sender, session)

            else:
                return '[unknown message scheme]', 'error'

            ctx = sender.encode('utf-8') + b'\x00' + self.username.encode('utf-8')
            text, status = open_signed(plain, self.peer_verify.get(sender), ctx)
            if sender in self.key_alerts:
                status = 'key_changed'
            return text.decode('utf-8'), status
        except Exception as e:
            return f'[error: {e}]', 'error'


# ═══════════════════════════════════════════════════════════════════════
# Хранилище сессий: username → UserMessenger
# ═══════════════════════════════════════════════════════════════════════

users_lock = threading.Lock()
users: dict[str, UserMessenger] = {}
# Временный кэш скачанных файлов: token → (data, filename, expires)
file_cache_lock = threading.Lock()
file_cache: dict[str, tuple] = {}
# Last seen timestamps: username → unix timestamp
last_seen_lock = threading.Lock()
last_seen: dict[str, float] = {}
# Last-seen privacy: username → 'everyone' | 'nobody' (default 'everyone')
last_seen_privacy: dict[str, str] = {}
# Profile photos: username → base64 data URL (stored on disk)
PROFILES_FILE = Path('.messenger_profiles.json')
transport = None
server_ip = '127.0.0.1'
server_port = 5353


def get_profiles() -> dict:
    return _load_json(PROFILES_FILE)


def save_profile_photo(username: str, photo: str):
    profiles = get_profiles()
    profiles[username] = {'photo': photo}
    _save_json(PROFILES_FILE, profiles)


def update_last_seen(username: str):
    with last_seen_lock:
        last_seen[username] = time.time()


# ── Safety number verification state (docs/ratchet-plan.md, фаза 3) ──────
# Не секрет (это лишь UI-пометка «я сверил число вслух/лично»), поэтому
# plaintext JSON рядом с профилями/webauthn-креды. Привязана к хешу ИМЕННО
# ТОГО бандла, что был сверен: если TOFU-пин пира потом сменится (см.
# _remember_peer/key_alerts), хеш перестанет совпадать и пометка сама
# перестанет действовать — отдельный код инвалидации не нужен.
def _verified_peers_file(username: str) -> Path:
    return Path(f'.messenger_{username}') / 'verified_peers.json'


def mark_peer_verified(username: str, peer: str, peer_bundle: bytes):
    path = _verified_peers_file(username)
    path.parent.mkdir(exist_ok=True)
    data = _load_json(path)
    data[peer] = {
        'bundle_hash': base64.b64encode(hashlib.sha256(peer_bundle).digest()).decode(),
        'verified_at': time.time(),
    }
    _save_json(path, data)


def clear_peer_verified(username: str, peer: str):
    path = _verified_peers_file(username)
    data = _load_json(path)
    if peer in data:
        del data[peer]
        _save_json(path, data)


def is_peer_verified(username: str, peer: str, peer_bundle: bytes) -> bool:
    entry = _load_json(_verified_peers_file(username)).get(peer)
    if not entry:
        return False
    expected = base64.b64encode(hashlib.sha256(peer_bundle).digest()).decode()
    return entry.get('bundle_hash') == expected


# ═══════════════════════════════════════════════════════════════════════
# Offline message buffer — stores messages while user's socket is disconnected
# ═══════════════════════════════════════════════════════════════════════

msg_buffer_lock = threading.Lock()
msg_buffer: dict[str, list] = {}          # username → [{'event': ..., 'data': ...}]
online_sockets: dict[str, int] = {}       # username → connected socket count


def buffer_or_emit(event: str, data: dict, username: str):
    """Emit to user if online, otherwise buffer for later delivery."""
    offline = False
    with msg_buffer_lock:
        if online_sockets.get(username, 0) > 0:
            socketio.emit(event, data, room=username)
        else:
            offline = True
            if username not in msg_buffer:
                msg_buffer[username] = []
            # Keep max 500 buffered messages per user
            if len(msg_buffer[username]) < 500:
                msg_buffer[username].append({'event': event, 'data': data})
    if offline:
        # Нет живого сокета — вкладка закрыта. Открытая-но-свёрнутая вкладка
        # рисует уведомление сама, здесь нужен именно серверный push.
        push_notify(username, event, data)


def flush_buffer(username: str):
    """Send all buffered messages to user."""
    with msg_buffer_lock:
        buf = msg_buffer.pop(username, [])
    for item in buf:
        socketio.emit(item['event'], item['data'], room=username)


# ═══════════════════════════════════════════════════════════════════════
# Web Push — уведомления при полностью закрытой вкладке
# ═══════════════════════════════════════════════════════════════════════

VAPID_FILE = Path('.messenger_vapid.json')
PUSH_FILE = Path('.messenger_push.json')
PUSH_SUBJECT = os.environ.get('PUSH_SUBJECT', 'mailto:admin@localhost')

vapid_keys = webpush.load_or_create_vapid(VAPID_FILE)
push_lock = threading.Lock()


def get_push_subs() -> dict:
    """{username: [subscription, ...]}"""
    return _load_json(PUSH_FILE)


def add_push_sub(username: str, sub: dict):
    with push_lock:
        subs = get_push_subs()
        mine = [s for s in subs.get(username, []) if s.get('endpoint') != sub.get('endpoint')]
        mine.append(sub)
        subs[username] = mine[-5:]   # не более 5 устройств на пользователя
        _save_json(PUSH_FILE, subs)


def remove_push_sub(username: str, endpoint: str):
    with push_lock:
        subs = get_push_subs()
        mine = [s for s in subs.get(username, []) if s.get('endpoint') != endpoint]
        if mine:
            subs[username] = mine
        else:
            subs.pop(username, None)
        _save_json(PUSH_FILE, subs)


def _push_body(event: str, data: dict) -> dict | None:
    """Текст уведомления. Само сообщение не кладём — push-сервис чужой."""
    sender = data.get('from') or '?'
    group = data.get('group')
    title = f'{sender} в {group}' if group else sender
    if event == 'file':
        return {'title': title, 'body': '📎 ' + (data.get('name') or 'файл'),
                'tag': group or sender}
    if event == 'message':
        return {'title': title, 'body': 'Новое сообщение', 'tag': group or sender}
    return None   # typing/read/status пушить незачем


def push_notify(username: str, event: str, data: dict):
    """Разослать push на все устройства пользователя. Не блокирует вызывающего."""
    body = _push_body(event, data)
    if not body:
        return
    subs = get_push_subs().get(username) or []
    if not subs:
        return

    def worker():
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        for sub in subs:
            try:
                webpush.send_push(sub, payload, vapid_keys, sub=PUSH_SUBJECT)
            except webpush.PushGone:
                remove_push_sub(username, sub.get('endpoint', ''))
            except Exception as e:
                # Push — дополнение к сокету, а не замена: сообщение уже
                # лежит в буфере, поэтому сбой здесь не должен ничего ронять.
                print(f'[push] {username}: {type(e).__name__}: {e}')

    threading.Thread(target=worker, daemon=True).start()


def get_messenger() -> UserMessenger | None:
    username = session.get('username')
    if not username:
        return None
    # Reject cookies issued before the user's most recent logout.
    if session.get('usv') != current_user_sv(username):
        return None
    with users_lock:
        m = users.get(username)
    if m:
        return m
    # Валидный cookie, но объекта нет — сервер перезапустили, а жил он только
    # в памяти. Пересобираем: ровно то, что сделал бы повторный вход, только
    # пользователя не выкидывает на экран логина посреди работы.
    return _restore_messenger(username, anon=bool(session.get('anon')))


def _restore_messenger(username: str, anon: bool = False) -> UserMessenger | None:
    if username in get_blocked():
        return None          # блокировку старый cookie обходить не должен
    with users_lock:
        m = users.get(username)
        if m:
            return m         # успели создать, пока ждали лок
        try:
            # anon: рестарт не должен вернуть anon'у ЕГО ЖЕ старую identity с
            # диска (там её и нет — persist_identity=False никогда её не писал)
            # и уж тем более не должен начать её персистить задним числом.
            m = UserMessenger(username, transport, persist_identity=not anon)
            if not m.register():
                return None
            users[username] = m
        except IdentityLocked:
            # Личность зашифрована паролем, а при авто-восстановлении его нет —
            # это НАМЕРЕННО: сервер не может пользоваться ключом без пароля.
            # Пусть пользователь войдёт заново (введёт пароль → расшифруем).
            print(f'[i] {username}: encrypted identity — re-login required after restart')
            return None
        except Exception as e:
            print(f'[!] Could not restore session for {username}: {e}')
            return None
    m.fetch_groups()
    start_poll_loop(m)
    print(f'[*] Session restored after restart: {username}')
    return m


# Экспоненциальный backoff с джиттером для цикла опроса. Причины две:
#   1) Скрытность: фиксированный «раз в 2 секунды» — характерный признак
#      DNS-туннеля для IDS. Дрожащий интервал ломает регулярность.
#   2) Экономия: в простое незачем долбить сервер каждые 2 с. При активности
#      возвращаемся к быстрому опросу немедленно.
POLL_MIN = 1.5          # сразу после сообщения — держим отзывчивость
POLL_MAX = 8.0          # потолок в простое: компромисс между скрытностью и
                        # задержкой push первого сообщения закрытому клиенту
POLL_JITTER = 0.4       # ±40% случайного разброса


def next_poll_delay(m: UserMessenger, got_message: bool) -> float:
    base = getattr(m, 'poll_interval', POLL_MIN)
    if got_message:
        base = POLL_MIN                       # есть трафик — опрашиваем часто
    else:
        base = min(base * 1.6, POLL_MAX)      # тишина — плавно замедляемся
    m.poll_interval = base
    return base * (1.0 + random.uniform(-POLL_JITTER, POLL_JITTER))


def start_poll_loop(m: UserMessenger):
    if m.running:
        return
    m.running = True

    def loop():
        cycle = 0
        while m.running:
            got = False
            try:
                for msg in m.poll_dm():
                    buffer_or_emit('message', msg, m.username); got = True
                for gid in list(m.group_keys):
                    for msg in m.poll_group(gid):
                        buffer_or_emit('message', msg, m.username); got = True
                for finfo in m.poll_files():
                    buffer_or_emit('file', finfo, m.username); got = True
                cycle += 1
                if cycle % 4 == 0:
                    # Реже, чем сообщения — не тайминг-критично: подхватывает
                    # ключ, разосланный чужим rekey_group (фаза 4,
                    # docs/ratchet-plan.md), и запускает децентрализованный
                    # ре-кей при добровольном leave (check_group_rekey).
                    m.fetch_groups()
                    m.check_group_rekey()
                m.poll_errors = 0
                update_last_seen(m.username)
                socketio.emit('status', {'connected': True}, room=m.username)
            except Exception:
                m.poll_errors += 1
                socketio.emit('status', {'connected': False, 'errors': m.poll_errors}, room=m.username)
            time.sleep(next_poll_delay(m, got))

    threading.Thread(target=loop, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════
# Flask-маршруты
# ═══════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    m = get_messenger()
    if not m:
        return render_template('login.html', server_ip=server_ip, server_port=server_port)
    return render_template('index.html', username=m.username, is_anon=bool(session.get('anon')))


@app.route('/sw.js')
def service_worker():
    """Serve the service worker from root so it can control the whole scope."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'sw.js')
    if os.path.isfile(path):
        with open(path, 'rb') as fh:
            resp = Response(fh.read(), mimetype='application/javascript')
            resp.headers['Service-Worker-Allowed'] = '/'
            resp.headers['Cache-Control'] = 'no-cache'
            return resp
    return Response('// not found', status=404, mimetype='application/javascript')


@app.route('/manifest.json')
def web_manifest():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'manifest.json')
    if os.path.isfile(path):
        with open(path, 'rb') as fh:
            return Response(fh.read(), mimetype='application/manifest+json')
    return Response('{}', status=404, mimetype='application/manifest+json')


@app.route('/<name>.txt')
def _ownership_proof(name):
    """Serve ownership/verification .txt files placed in ./proof/ at the web root."""
    safe = ''.join(ch for ch in name if ch.isalnum() or ch in '-_')
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'proof',
                        f'{safe}.txt')
    if os.path.isfile(path):
        with open(path, 'rb') as fh:
            return Response(fh.read(), mimetype='text/plain')
    return Response('not found\n', status=404, mimetype='text/plain')


@app.route('/api/relay/status')
def api_relay_status():
    """Реальная (не декоративная) проверка живости реле для экрана входа —
    один дешёвый getkey-запрос на заведомо несуществующее имя, с замером
    фактической задержки round-trip. Неаутентифицирован по необходимости
    (полезен ИМЕННО до входа), поэтому — жёсткий rate limit per-IP: иначе
    HTTP-флуд на этот роут превращается в бесплатный UDP-флуд нашего же
    реле (тот же класс проблемы, что и amplification, только жертва — мы
    сами, а не третья сторона).
    """
    if rate_limited(f'relay-status:{client_ip()}', max_attempts=20, window_seconds=60.0):
        return jsonify({'ok': False, 'error': 'rate_limited'}), 429
    if transport is None:
        return jsonify({'ok': False})
    started = time.time()
    try:
        res = transport.query([CMD_GETKEY, '__relay_status_probe__'])
    except Exception:
        return jsonify({'ok': False})
    latency_ms = round((time.time() - started) * 1000)
    # Белый, не чёрный список: getkey на несуществующее имя УСПЕШНО отвечает
    # 'ERR:not_found' — это тоже 'ERR:', но означает «реле живо и ответило»,
    # а не «не достучались». Любой другой ответ (таймаут/нет транспорта/
    # текст исключения DoH) означает реальную проблему связи — их безопаснее
    # перечислить явно как единственный успех, чем пытаться угадать и
    # перечислить все возможные строки-неудачи.
    ok = res == 'ERR:not_found'
    return jsonify({'ok': ok, 'latency_ms': latency_ms})


@app.route('/api/login', methods=['POST'])
def api_login():
    if rate_limited(f'login:{client_ip()}', max_attempts=10, window_seconds=60.0):
        return jsonify({'ok': False, 'error': 'Too many attempts. Try again later.'}), 429
    d = get_json_dict()
    username = str(d.get('username') or '').strip().lower()
    password = str(d.get('password') or '').strip()
    mode = d.get('mode', 'anonymous')  # 'register', 'login', 'anonymous'
    if not isinstance(mode, str):
        mode = 'anonymous'

    if not username:
        return jsonify({'ok': False, 'error': 'Enter a username'})
    if len(username) < 2 or len(username) > 20:
        return jsonify({'ok': False, 'error': 'Username: 2-20 characters'})
    if not all(c.isascii() and (c.isalnum() or c == '_') for c in username):
        return jsonify({'ok': False, 'error': 'Only latin letters, digits and _'})
    if username == 'admin':
        return jsonify({'ok': False, 'error': 'Reserved username'})

    # Проверка блокировки
    if username in get_blocked():
        return jsonify({'ok': False, 'error': 'Account is blocked'})

    accounts = get_accounts()

    if mode == 'register':
        if not password or len(password) < 8:
            return jsonify({'ok': False, 'error': 'Password: minimum 8 characters'})
        if username in accounts:
            return jsonify({'ok': False, 'error': 'Username already registered'})
        h, s = _hash_password(password)
        save_account(username, h, s)
        print(f'[+] Registered: {username}')

    elif mode == 'login':
        if username not in accounts:
            return jsonify({'ok': False, 'error': 'Account not found. Register first.'})
        # Пер-аккаунтный троттлинг: закрывает брутфорс с ротацией IP, который
        # обходит пер-IP лимит.
        if account_throttled(username):
            return jsonify({'ok': False, 'error': 'Too many failed attempts. Try again later.'}), 429
        acc = accounts[username]
        if not _verify_password(password, acc['hash'], acc['salt']):
            note_login_failure(username)
            return jsonify({'ok': False, 'error': 'Wrong password'})

    else:  # anonymous
        if username in accounts:
            return jsonify({'ok': False, 'error': 'This username is registered. Enter password or choose another name.'})

    # Пароль аккаунта шифрует identity-файл на диске (только для register/login;
    # у анонима пароля нет). Ошибка расшифровки => неверный пароль к личности.
    id_pw = password if mode in ('register', 'login') else None

    with users_lock:
        m = users.get(username)
        if mode == 'anonymous' and m:
            # Анонимы не аутентифицированы паролем, поэтому имя не может быть
            # общим ключом идентификации между сессиями: если бы второй claim
            # того же ника молча получал ТОТ ЖЕ уже активный UserMessenger, кто
            # угодно перехватил бы живую анонимную сессию, просто введя тот же
            # ник — без единого пароля. Проверка и создание — под одним и тем
            # же логом, иначе гонка двух одновременных anon-логинов с
            # одинаковым ником всё равно даёт второму объект первого.
            return jsonify({'ok': False, 'error': 'This name is in use right now. Choose another.'})
        if not m:
            try:
                m = UserMessenger(username, transport, password=id_pw,
                                   persist_identity=(mode != 'anonymous'))
                if not m.register():
                    return jsonify({'ok': False, 'error': 'Relay server unavailable'})
                users[username] = m
            except IdentityLocked:
                return jsonify({'ok': False, 'error': 'Wrong password'})
            except Exception as e:
                return jsonify({'ok': False, 'error': str(e)})

    # Второй фактор: если у аккаунта есть хоть один зарегистрированный passkey,
    # пароль подтверждает ТОЛЬКО личность — сессию выдаём только после
    # webauthn-подтверждения (см. /api/webauthn/login/*). Анонимный режим
    # исключён: там и пароля-то нет. m уже создан и зарегистрирован на релее
    # (нужен для webauthn/login/verify, который найдёт его в users[...] по
    # имени), просто сессионную куку пока не выдаём.
    if mode != 'anonymous' and user_webauthn_creds(username):
        session['pending_2fa_user'] = username
        session['pending_2fa_exp'] = time.time() + PENDING_2FA_TTL
        return jsonify({'ok': True, 'need_webauthn': True})

    m.fetch_groups()
    start_poll_loop(m)
    session['username'] = username
    session['usv'] = current_user_sv(username)
    # Нужно для восстановления сессии после рестарта (_restore_messenger):
    # анонимная сессия не должна получить персистентную (диск-загружаемую)
    # identity даже после рестарта — иначе A2 воспроизводится через рестарт.
    session['anon'] = (mode == 'anonymous')
    print(f'[+] Login: {username} ({mode})')
    return jsonify({'ok': True})


def _finish_login(username: str):
    """Общий хвост успешного входа — то, что api_login делает сразу, а
    webauthn/login/verify делает после подтверждения passkey."""
    with users_lock:
        m = users.get(username)
    if not m:
        return False
    m.fetch_groups()
    start_poll_loop(m)
    session['username'] = username
    session['usv'] = current_user_sv(username)
    session['anon'] = False
    session.pop('pending_2fa_user', None)
    session.pop('pending_2fa_exp', None)
    print(f'[+] Login: {username} (webauthn)')
    return True


# ── WebAuthn (passkey) — второй фактор для register/login-аккаунтов ────
# Пароль доказывает "я знаю секрет", passkey доказывает "у меня физическое
# устройство/биометрия" — второй фактор, не замена пароля. Приватный ключ
# passkey никогда не покидает устройство и никогда не приходит на сервер;
# сервер хранит только публичный ключ и счётчик подписей.

@app.route('/api/webauthn/register/options', methods=['POST'])
def api_webauthn_register_options():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'}), 401
    if session.get('anon'):
        # Анонимный аккаунт не имеет пароля — passkey тут не «второй
        # фактор», а бессмысленный придаток к одноразовой identity (A2:
        # анонимная identity не переживает даже следующий логин тем же
        # ником, так что сохранённый passkey никогда не будет проверен).
        return jsonify({'ok': False, 'error': 'Not available for anonymous accounts'}), 403
    rp_id, _origin = webauthn_rp()
    exclude = [
        PublicKeyCredentialDescriptor(id=webauthn.base64url_to_bytes(c['id']))
        for c in user_webauthn_creds(m.username)
    ]
    options = webauthn.generate_registration_options(
        rp_id=rp_id, rp_name='DNS Messenger',
        user_name=m.username, user_id=m.username.encode('utf-8'),
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED),
    )
    session['wa_reg_challenge'] = base64.b64encode(options.challenge).decode('ascii')
    session['wa_reg_exp'] = time.time() + WEBAUTHN_CHALLENGE_TTL
    session['wa_reg_user'] = m.username
    return Response(webauthn.options_to_json(options), mimetype='application/json')


@app.route('/api/webauthn/register/verify', methods=['POST'])
def api_webauthn_register_verify():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'}), 401
    challenge_b64 = session.get('wa_reg_challenge')
    exp = session.get('wa_reg_exp', 0)
    # wa_reg_user привязывает challenge к тому, кто его запросил: иначе можно
    # было бы начать церемонию под одним логином, а подтвердить под другим,
    # если оба открыты в одной сессии/вкладке одновременно.
    if not challenge_b64 or time.time() > exp or session.get('wa_reg_user') != m.username:
        return jsonify({'ok': False, 'error': 'Registration ceremony expired, try again'})
    d = get_json_dict()
    label = str(d.get('label') or 'Passkey').strip()
    try:
        verification = webauthn.verify_registration_response(
            credential=d.get('credential'),
            expected_challenge=base64.b64decode(challenge_b64),
            expected_rp_id=webauthn_rp()[0],
            expected_origin=webauthn_rp()[1],
            require_user_verification=True,
        )
    except WebAuthnException as e:
        return jsonify({'ok': False, 'error': f'Verification failed: {e}'})
    finally:
        session.pop('wa_reg_challenge', None)
        session.pop('wa_reg_exp', None)
        session.pop('wa_reg_user', None)
    is_first_credential = not user_webauthn_creds(m.username)
    save_webauthn_cred(
        m.username,
        webauthn.helpers.bytes_to_base64url(verification.credential_id),
        base64.b64encode(verification.credential_public_key).decode('ascii'),
        verification.sign_count, label,
    )
    resp = {'ok': True}
    # Первый passkey на аккаунте включает требование второго фактора — без
    # запасного пути один потерянный/сломанный аутентификатор означает
    # безвозвратную потерю аккаунта (пароль всё ещё известен, но сессию он
    # больше не даёт). Коды выдаются РОВНО ОДИН РАЗ, сразу здесь.
    if is_first_credential:
        resp['backup_codes'] = generate_backup_codes(m.username)
    return jsonify(resp)


@app.route('/api/webauthn/credentials')
def api_webauthn_credentials():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'}), 401
    creds = [{'id': c['id'], 'label': c['label'], 'added_ts': c['added_ts']}
             for c in user_webauthn_creds(m.username)]
    return jsonify({'ok': True, 'credentials': creds})


@app.route('/api/webauthn/credentials/remove', methods=['POST'])
def api_webauthn_credentials_remove():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'}), 401
    cred_id = str(get_json_dict().get('id') or '')
    ok = remove_webauthn_cred(m.username, cred_id)
    return jsonify({'ok': ok})


@app.route('/api/webauthn/backup-codes/status')
def api_backup_codes_status():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'}), 401
    remaining, total = backup_codes_status(m.username)
    return jsonify({'ok': True, 'remaining': remaining, 'total': total})


@app.route('/api/webauthn/backup-codes/generate', methods=['POST'])
def api_backup_codes_generate():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'}), 401
    if not user_webauthn_creds(m.username):
        # Коды без единого passkey бессмысленны: 2FA не требуется, вход и так
        # только по паролю, а «запасной путь» к 2FA, которой нет, не нужен.
        return jsonify({'ok': False, 'error': 'Add a passkey first'}), 400
    codes = generate_backup_codes(m.username)
    return jsonify({'ok': True, 'codes': codes})


@app.route('/api/recovery/status')
def api_recovery_status():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'}), 401
    if not m.persist_identity:
        return jsonify({'ok': True, 'available': False, 'has_code': False})
    return jsonify({'ok': True, 'available': True, 'has_code': has_recovery_code(m.username)})


@app.route('/api/recovery/generate', methods=['POST'])
def api_recovery_generate():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'}), 401
    if not m.persist_identity:
        # Аноним не персистит identity вообще — восстанавливать нечего.
        return jsonify({'ok': False, 'error': 'Not available in anonymous mode'}), 400
    code = generate_recovery_code(m.username, m.identity)
    return jsonify({'ok': True, 'code': code})


@app.route('/api/recovery/reset', methods=['POST'])
def api_recovery_reset():
    # Код восстановления — по сути второй пароль (расшифровывает identity),
    # поэтому лимитируем перебор так же жёстко, как /api/login: и по IP, и
    # по аккаунту отдельно (ротация IP не должна снимать лимит).
    if rate_limited(f'recovery:{client_ip()}', max_attempts=10, window_seconds=300.0):
        return jsonify({'ok': False, 'error': 'Too many attempts. Try again later.'}), 429
    d = get_json_dict()
    username = str(d.get('username') or '').strip().lower()
    code = str(d.get('code') or '')
    new_password = str(d.get('new_password') or '').strip()
    if not username or not code:
        return jsonify({'ok': False, 'error': 'Enter the username and recovery code'})
    if len(new_password) < 8:
        return jsonify({'ok': False, 'error': 'Password: minimum 8 characters'})
    if username in get_blocked():
        return jsonify({'ok': False, 'error': 'Account is blocked'})
    # Один и тот же общий ответ на «нет такого юзера» и «код неверный» —
    # иначе строка ошибки палит существование аккаунта.
    generic_err = jsonify({'ok': False, 'error': 'Invalid username or recovery code'})
    if username not in get_accounts():
        return generic_err
    if account_throttled(username):
        return jsonify({'ok': False, 'error': 'Too many attempts. Try again later.'}), 429
    identity = consume_recovery_code(username, code)
    if identity is None:
        note_login_failure(username)
        return generic_err
    key_file = Path(f'.messenger_{username}') / 'identity.key'
    identity.save(str(key_file), new_password)
    h, s = _hash_password(new_password)
    save_account(username, h, s)
    # Код одноразовый: сразу выпускаем новый, старый (уже потраченный) больше
    # ничего не расшифрует.
    new_code = generate_recovery_code(username, identity)
    # Пароль сменился «в обход» обычного логина — на всякий случай гасим
    # любые уже выданные куки этого аккаунта, как при обычном логауте.
    bump_user_sv(username)
    print(f'[+] Account recovered via recovery code: {username}')
    return jsonify({'ok': True, 'code': new_code})


@app.route('/api/webauthn/login/backup', methods=['POST'])
def api_webauthn_login_backup():
    if rate_limited(f'webauthn:{client_ip()}', max_attempts=15, window_seconds=60.0):
        return jsonify({'ok': False, 'error': 'Too many attempts. Try again later.'}), 429
    username = pending_2fa_user()
    if not username:
        return jsonify({'ok': False, 'error': 'No pending login'}), 401
    code = str(get_json_dict().get('code') or '')
    if not consume_backup_code(username, code):
        return jsonify({'ok': False, 'error': 'Invalid or already-used code'})
    if not _finish_login(username):
        return jsonify({'ok': False, 'error': 'Session expired, log in again'})
    return jsonify({'ok': True})


@app.route('/api/webauthn/login/options', methods=['POST'])
def api_webauthn_login_options():
    if rate_limited(f'webauthn:{client_ip()}', max_attempts=15, window_seconds=60.0):
        return jsonify({'ok': False, 'error': 'Too many attempts. Try again later.'}), 429
    username = pending_2fa_user()
    if not username:
        return jsonify({'ok': False, 'error': 'No pending login'}), 401
    creds = user_webauthn_creds(username)
    allow = [PublicKeyCredentialDescriptor(id=webauthn.base64url_to_bytes(c['id']))
             for c in creds]
    options = webauthn.generate_authentication_options(
        rp_id=webauthn_rp()[0], allow_credentials=allow,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    session['wa_auth_challenge'] = base64.b64encode(options.challenge).decode('ascii')
    session['wa_auth_exp'] = time.time() + WEBAUTHN_CHALLENGE_TTL
    return Response(webauthn.options_to_json(options), mimetype='application/json')


@app.route('/api/webauthn/login/verify', methods=['POST'])
def api_webauthn_login_verify():
    if rate_limited(f'webauthn:{client_ip()}', max_attempts=15, window_seconds=60.0):
        return jsonify({'ok': False, 'error': 'Too many attempts. Try again later.'}), 429
    username = pending_2fa_user()
    challenge_b64 = session.get('wa_auth_challenge')
    exp = session.get('wa_auth_exp', 0)
    if not username or not challenge_b64 or time.time() > exp:
        return jsonify({'ok': False, 'error': 'Login ceremony expired, try again'})
    d = get_json_dict()
    credential = d.get('credential') or {}
    raw_id = str(credential.get('id') or credential.get('rawId') or '')
    stored = next((c for c in user_webauthn_creds(username) if c['id'] == raw_id), None)
    if not stored:
        return jsonify({'ok': False, 'error': 'Unknown credential'})
    try:
        verification = webauthn.verify_authentication_response(
            credential=credential,
            expected_challenge=base64.b64decode(challenge_b64),
            expected_rp_id=webauthn_rp()[0],
            expected_origin=webauthn_rp()[1],
            credential_public_key=base64.b64decode(stored['public_key']),
            credential_current_sign_count=stored['sign_count'],
            require_user_verification=True,
        )
    except WebAuthnException as e:
        return jsonify({'ok': False, 'error': f'Verification failed: {e}'})
    finally:
        session.pop('wa_auth_challenge', None)
        session.pop('wa_auth_exp', None)
    update_webauthn_sign_count(username, raw_id, verification.new_sign_count)
    if not _finish_login(username):
        return jsonify({'ok': False, 'error': 'Session expired, log in again'})
    return jsonify({'ok': True})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    username = session.pop('username', None)
    session.pop('usv', None)
    if username:
        # Bump the session-version so the cookie just cleared (and any other
        # copy of it, captured before this call) can never be replayed again.
        bump_user_sv(username)
        # Анонимная identity не персистентна (persist_identity=False) и не
        # должна пережить логаут ни на диске, ни в памяти — иначе тот же
        # объект (и открытая для этого ника identity/переписка) достался бы
        # следующему, кто просто введёт тот же ник, что и есть сам A2. Заодно
        # освобождает ник для повторного анонимного использования.
        with users_lock:
            m = users.get(username)
            if m is not None and not m.persist_identity:
                users.pop(username, None)
                m.running = False
        print(f'[-] Logout: {username}')
    return jsonify({'ok': True})


@app.route('/api/me')
def api_me():
    m = get_messenger()
    if not m:
        return jsonify({'logged_in': False})
    return jsonify({'logged_in': True, 'username': m.username})


# ── DM ───────────────────────────────────────────────────────────────

@app.route('/api/send', methods=['POST'])
def api_send():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'})
    d = get_json_dict()
    to = d.get('to')
    text = d.get('text')
    if not to or not text:
        return jsonify({'ok': False, 'error': 'Missing "to" or "text"'}), 400
    return jsonify(m.send_dm(to, text))


@app.route('/api/resolve', methods=['POST'])
def api_resolve():
    m = get_messenger()
    if not m:
        return jsonify({'found': False, 'error': 'Not authorized'})
    user = str(get_json_dict().get('user') or '').strip().lower()
    if not user:
        return jsonify({'found': False, 'error': 'Empty name'})
    if user == m.username:
        return jsonify({'found': False, 'error': 'Cannot message yourself'})
    pk = m.get_peer_key(user)
    if pk:
        return jsonify({'found': True, 'user': user})
    return jsonify({'found': False, 'error': f'"{user}" not found. Must sign in first.'})


def _safety_number_peer_bundle(m: 'UserMessenger', peer: str) -> bytes | None:
    """Пин пира (X25519+Ed25519) как единый бандл, или None — либо пир не
    найден, либо у него нет Ed25519 (легаси-бандл без подписи, до фазы 1)."""
    pk = m.get_peer_key(peer)     # тянет/подтверждает TOFU-пин
    if not pk:
        return None
    ed = m.peer_verify.get(peer)
    if not ed:
        return None
    return pk + ed


@app.route('/api/safety-number/<peer>')
def api_safety_number(peer):
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'})
    peer = str(peer).strip().lower()
    if peer == m.username:
        return jsonify({'ok': False, 'error': 'Cannot compare with yourself'})
    peer_bundle = _safety_number_peer_bundle(m, peer)
    if not peer_bundle:
        return jsonify({'ok': False, 'error': f'"{peer}" not found or has no signing key'})
    digits = safety_number(m.username, m.identity.public_bundle(), peer, peer_bundle)
    return jsonify({
        'ok': True,
        'peer': peer,
        'number': format_safety_number(digits),
        'verified': is_peer_verified(m.username, peer, peer_bundle),
    })


@app.route('/api/safety-number/<peer>/verify', methods=['POST'])
def api_safety_number_verify(peer):
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'})
    peer = str(peer).strip().lower()
    peer_bundle = _safety_number_peer_bundle(m, peer)
    if not peer_bundle:
        return jsonify({'ok': False, 'error': f'"{peer}" not found or has no signing key'})
    verified = bool(get_json_dict().get('verified'))
    if verified:
        mark_peer_verified(m.username, peer, peer_bundle)
    else:
        clear_peer_verified(m.username, peer)
    return jsonify({'ok': True, 'verified': verified})


# ── Группы ───────────────────────────────────────────────────────────

@app.route('/api/groups')
def api_groups():
    m = get_messenger()
    if not m:
        return jsonify({'groups': []})
    m.fetch_groups()
    return jsonify({'groups': list(m.group_keys.keys())})


@app.route('/api/groups/create', methods=['POST'])
def api_group_create():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'})
    gid = str(get_json_dict().get('group') or '').strip().lower()
    if not gid:
        return jsonify({'ok': False, 'error': 'Enter group name'})
    if len(gid) < 2 or len(gid) > 32:
        return jsonify({'ok': False, 'error': 'Name: 2-32 characters'})
    if not all(c.isascii() and (c.isalnum() or c == '_') for c in gid):
        return jsonify({'ok': False, 'error': 'Only latin letters, digits and _ (DNS limit)'})
    ok = m.create_group(gid)
    if not ok:
        return jsonify({'ok': False, 'error': 'Failed — group may already exist'})
    # Return the canonical (lowercased) id so the client stores the same key the
    # server will report from /api/groups — avoids duplicate chat entries.
    return jsonify({'ok': True, 'group': gid})


@app.route('/api/groups/invite', methods=['POST'])
def api_group_invite():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False})
    d = get_json_dict()
    group = d.get('group')
    user = d.get('user')
    if not group or not user:
        return jsonify({'ok': False, 'error': 'Missing "group" or "user"'}), 400
    return jsonify(m.invite_to_group(group, user))


@app.route('/api/groups/send', methods=['POST'])
def api_group_send():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False})
    d = get_json_dict()
    group = d.get('group')
    text = d.get('text')
    if not group or not text:
        return jsonify({'ok': False, 'error': 'Missing "group" or "text"'}), 400
    return jsonify({'ok': m.send_group(group, text)})


@app.route('/api/groups/members')
def api_group_members():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'members': []})
    group = str(request.args.get('group') or '').strip().lower()
    if not group:
        return jsonify({'ok': False, 'error': 'Missing "group"', 'members': []}), 400
    return jsonify({'ok': True, 'members': m.list_group_members(group)})


@app.route('/api/groups/leave', methods=['POST'])
def api_group_leave():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False})
    group = str(get_json_dict().get('group') or '').strip().lower()
    if not group:
        return jsonify({'ok': False, 'error': 'Missing "group"'}), 400
    ok = m.leave_group(group)
    return jsonify({'ok': ok, 'error': '' if ok else 'Error'})


@app.route('/api/groups/kick', methods=['POST'])
def api_group_kick():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False})
    d = get_json_dict()
    group = str(d.get('group') or '').strip().lower()
    target = str(d.get('user') or '').strip().lower()
    if not group or not target:
        return jsonify({'ok': False, 'error': 'Missing "group" or "user"'}), 400
    if target == m.username:
        return jsonify({'ok': False, 'error': 'Use leave, not kick, to remove yourself'})
    return jsonify(m.kick_member(group, target))


# ── Пользователи ────────────────────────────────────────────────

@app.route('/api/users')
def api_users():
    m = get_messenger()
    if not m:
        return jsonify({'users': []})
    try:
        all_users = m.list_users()
        blocked = get_blocked()
        return jsonify({'users': [u for u in all_users if u != m.username and u not in blocked]})
    except Exception:
        return jsonify({'users': []})


# ── Last seen ───────────────────────────────────────────────────────

@app.route('/api/push/key')
def api_push_key():
    """Публичный VAPID-ключ для applicationServerKey."""
    return jsonify({'ok': True, 'key': vapid_keys['public']})


@app.route('/api/push/subscribe', methods=['POST'])
def api_push_subscribe():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'})
    sub = get_json_dict().get('subscription') or {}
    keys = sub.get('keys') or {}
    if not sub.get('endpoint') or not keys.get('p256dh') or not keys.get('auth'):
        return jsonify({'ok': False, 'error': 'Invalid subscription'})
    # SSRF-заслон: без него любой залогиненный пользователь мог бы подписать
    # сервер на внутренний адрес/облачные метаданные и дёргать его как прокси
    # через /api/push/test.
    if not webpush.is_safe_push_endpoint(sub['endpoint']):
        return jsonify({'ok': False, 'error': 'Invalid subscription'})
    add_push_sub(m.username, {'endpoint': sub['endpoint'],
                              'keys': {'p256dh': keys['p256dh'], 'auth': keys['auth']}})
    return jsonify({'ok': True})


@app.route('/api/push/unsubscribe', methods=['POST'])
def api_push_unsubscribe():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'})
    endpoint = get_json_dict().get('endpoint') or ''
    if endpoint:
        remove_push_sub(m.username, endpoint)
    return jsonify({'ok': True})


@app.route('/api/push/test', methods=['POST'])
def api_push_test():
    """Отправить себе пробное уведомление — проверка сквозной цепочки."""
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'})
    subs = get_push_subs().get(m.username) or []
    if not subs:
        return jsonify({'ok': False, 'error': 'No subscriptions'})
    payload = json.dumps({'title': 'DNS Messenger',
                          'body': 'Пробное уведомление', 'tag': 'push-test'},
                         ensure_ascii=False).encode('utf-8')
    sent, errors = 0, []
    for sub in subs:
        try:
            webpush.send_push(sub, payload, vapid_keys, sub=PUSH_SUBJECT)
            sent += 1
        except webpush.PushGone:
            remove_push_sub(m.username, sub.get('endpoint', ''))
            errors.append('gone')
        except Exception as e:
            errors.append(f'{type(e).__name__}: {e}')
    return jsonify({'ok': sent > 0, 'sent': sent, 'errors': errors})


@app.route('/api/privacy/last-seen', methods=['POST'])
def api_privacy_last_seen():
    """Set the current user's last-seen visibility preference."""
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'})
    vis = get_json_dict().get('visibility', 'everyone')
    if vis not in ('everyone', 'nobody'):
        return jsonify({'ok': False, 'error': 'Invalid value'})
    with last_seen_lock:
        last_seen_privacy[m.username] = vis
    return jsonify({'ok': True})


@app.route('/api/last-seen/<username>')
def api_last_seen(username):
    m = get_messenger()
    if not m:
        return jsonify({'online': False})
    with users_lock:
        is_online = username in users and users[username].running
    with last_seen_lock:
        ts = last_seen.get(username)
        vis = last_seen_privacy.get(username, 'everyone')
    # Hidden: still show "online" if actually online, but no timestamp
    if vis == 'nobody' and username != m.username:
        return jsonify({'online': is_online, 'last_seen': None, 'hidden': True})
    return jsonify({
        'online': is_online,
        'last_seen': ts,
    })


@app.route('/api/last-seen-batch', methods=['POST'])
def api_last_seen_batch():
    """Get last seen for multiple users at once."""
    m = get_messenger()
    if not m:
        return jsonify({})
    usernames = get_json_dict().get('users', [])
    if not isinstance(usernames, list):
        usernames = []
    result = {}
    with users_lock:
        online_set = {u for u, um in users.items() if um.running}
    with last_seen_lock:
        for u in usernames:
            vis = last_seen_privacy.get(u, 'everyone')
            if vis == 'nobody' and u != m.username:
                result[u] = {'online': u in online_set, 'last_seen': None, 'hidden': True}
            else:
                result[u] = {
                    'online': u in online_set,
                    'last_seen': last_seen.get(u),
                }
    return jsonify(result)


# ── Profile photos ──────────────────────────────────────────────────

@app.route('/api/profile/photo', methods=['POST'])
def api_profile_photo_set():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'})
    photo = get_json_dict().get('photo', '')
    if not isinstance(photo, str):
        return jsonify({'ok': False, 'error': 'Invalid image format'}), 400
    # startswith('data:image/') alone lets anything follow the prefix — e.g.
    # `data:image/png,x" onerror="..."` — which the client used to interpolate
    # unescaped into <img src="...">, a real stored XSS (proven live: a crafted
    # photo fired script in a victim's browser via the chat/avatar view before
    # this fix + the matching client-side esc() fix landed). Require the full
    # base64 data-URL shape instead of a bare prefix check.
    if photo and not PHOTO_DATA_URL_RE.match(photo):
        return jsonify({'ok': False, 'error': 'Invalid image format'})
    if len(photo) > 150_000:
        return jsonify({'ok': False, 'error': 'Image too large (max ~100KB)'})
    save_profile_photo(m.username, photo)
    return jsonify({'ok': True})


@app.route('/api/profile/photo/<username>')
def api_profile_photo_get(username):
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'}), 401
    profiles = get_profiles()
    p = profiles.get(username, {})
    return jsonify({'photo': p.get('photo', '')})


@app.route('/api/profile/photos', methods=['POST'])
def api_profile_photos_batch():
    """Get photos for multiple users at once. Requires an authenticated session."""
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'}), 401
    usernames = get_json_dict().get('users', [])
    if not isinstance(usernames, list):
        usernames = []
    profiles = get_profiles()
    result = {}
    for u in usernames:
        p = profiles.get(u, {})
        result[u] = p.get('photo', '')
    return jsonify(result)


# ── Файлы ────────────────────────────────────────────────────────────

@app.route('/api/file/send', methods=['POST'])
def api_file_send():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False, 'error': 'Not authorized'})
    to_user = request.form.get('to', '')
    f = request.files.get('file')
    if not f:
        return jsonify({'ok': False, 'error': 'No file selected'})
    if not to_user:
        return jsonify({'ok': False, 'error': 'No recipient'})
    data = f.read()
    if len(data) > 512 * 1024:
        return jsonify({'ok': False, 'error': 'Max 512 KB'})
    return jsonify(m.send_file(to_user, f.filename, data))


@app.route('/api/file/download', methods=['POST'])
def api_file_download():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False})
    d = get_json_dict()
    fid = d.get('fid')
    frm = d.get('from')
    if not fid or not frm:
        return jsonify({'ok': False, 'error': 'Missing "fid" or "from"'}), 400
    result = m.download_file(fid, frm)
    if result is None:
        return jsonify({'ok': False})
    # Сохранить в кэш для GET-загрузки (мобильные браузеры)
    token = secrets.token_urlsafe(16)
    filename = d.get('filename', 'file')
    with file_cache_lock:
        file_cache[token] = (result, filename, time.time() + 120)
    return jsonify({'ok': True, 'token': token,
                    'data': base64.b64encode(result).decode('ascii')})


@app.route('/api/file/get/<token>')
def api_file_get(token):
    """GET-эндпоинт для скачивания файлов на мобильных устройствах."""
    with file_cache_lock:
        entry = file_cache.pop(token, None)
    if not entry:
        return 'File not found or expired', 404
    data, filename, expires = entry
    if time.time() > expires:
        return 'Download link expired', 410
    # filename пришёл от клиента (расшифрованное E2E-имя файла, но сама строка
    # не проверена) и раньше шёл прямо в заголовок без экранирования — кавычка
    # или служебный символ внутри могли сломать разбор Content-Disposition
    # браузером. secure_filename режет до safe ASCII (без путей/кавычек/CR-LF).
    safe_name = secure_filename(filename) or 'file'
    return Response(
        data,
        mimetype='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename="{safe_name}"'},
    )


# ── Админ-панель ────────────────────────────────────────────────────

@app.route('/admin')
def admin_page():
    if not is_admin_session():
        return render_template('admin_login.html')
    return render_template('admin.html')


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    if rate_limited(f'admin_login:{client_ip()}', max_attempts=5, window_seconds=60.0):
        return jsonify({'ok': False, 'error': 'Too many attempts. Try again later.'}), 429
    password = str(get_json_dict().get('password') or '')
    admin_data = _load_json(ADMIN_FILE)
    if not admin_data:
        return jsonify({'ok': False, 'error': 'Admin not configured'})
    if not _verify_password(password, admin_data['hash'], admin_data['salt']):
        return jsonify({'ok': False, 'error': 'Wrong password'})
    session['is_admin'] = True
    session['sv'] = admin_data.get('sv', 0)
    return jsonify({'ok': True, 'change_required': admin_data.get('change_required', False)})


@app.route('/api/admin/change-password', methods=['POST'])
def admin_change_password():
    if not is_admin_session():
        return jsonify({'ok': False, 'error': 'Not authorized'})
    new_pw = str(get_json_dict().get('password') or '')
    if len(new_pw) < 8:
        return jsonify({'ok': False, 'error': 'Minimum 8 characters'})
    admin_data = _load_json(ADMIN_FILE)
    h, s = _hash_password(new_pw)
    new_sv = admin_data.get('sv', 0) + 1
    _save_json(ADMIN_FILE, {'hash': h, 'salt': s, 'change_required': False, 'sv': new_sv})
    session['sv'] = new_sv
    return jsonify({'ok': True})


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    # Bump the session-version so the cookie just cleared (and any other
    # copy of it, forged or genuine) can never be replayed for admin access.
    #
    # Gated on is_admin_session(): 'sv' is a single global counter for the one
    # admin account, so without this check any anonymous POST here would kick
    # the real admin out — a no-auth-required denial of service against them.
    if is_admin_session():
        admin_data = _load_json(ADMIN_FILE)
        if admin_data:
            admin_data['sv'] = admin_data.get('sv', 0) + 1
            _save_json(ADMIN_FILE, admin_data)
    session.pop('is_admin', None)
    session.pop('sv', None)
    return jsonify({'ok': True})


@app.route('/api/admin/users')
def admin_users():
    if not is_admin_session():
        return jsonify({'ok': False})
    accounts = get_accounts()
    blocked = get_blocked()
    with users_lock:
        online = list(users.keys())
    all_users = set(online) | set(accounts.keys())
    result = []
    for u in sorted(all_users):
        result.append({
            'username': u,
            'registered': u in accounts,
            'online': u in online,
            'blocked': u in blocked,
        })
    return jsonify({'ok': True, 'users': result})


@app.route('/api/admin/block', methods=['POST'])
def admin_block():
    if not is_admin_session():
        return jsonify({'ok': False})
    username = str(get_json_dict().get('username') or '')
    blocked = get_blocked()
    blocked.add(username)
    save_blocked(blocked)
    # Остановить поллинг
    with users_lock:
        m = users.get(username)
        if m:
            m.running = False
    # Инвалидировать уже выданные cookie: get_messenger() сверяет только usv,
    # а blocked-множество проверяется лишь при логине и при восстановлении
    # сессии после рестарта сервера. Без bump'а уже залогиненный пользователь
    # продолжал бы полноценно слать сообщения и файлы до ближайшего рестарта.
    bump_user_sv(username)
    print(f'[ADMIN] Blocked: {username}')
    return jsonify({'ok': True})


@app.route('/api/admin/unblock', methods=['POST'])
def admin_unblock():
    if not is_admin_session():
        return jsonify({'ok': False})
    username = str(get_json_dict().get('username') or '')
    blocked = get_blocked()
    blocked.discard(username)
    save_blocked(blocked)
    print(f'[ADMIN] Unblocked: {username}')
    return jsonify({'ok': True})


@app.route('/api/admin/delete', methods=['POST'])
def admin_delete():
    if not is_admin_session():
        return jsonify({'ok': False})
    username = str(get_json_dict().get('username') or '')
    # Удалить аккаунт
    accounts = get_accounts()
    accounts.pop(username, None)
    _save_json(ACCOUNTS_FILE, accounts)
    # Остановить поллинг
    with users_lock:
        m = users.pop(username, None)
        if m:
            m.running = False
    # identity.key/recovery/passkeys/backup-коды/фото — иначе ник, отданный
    # заново другому человеку, либо унаследует чужие данные, либо (при
    # зашифрованном identity под чужим паролем) вообще не сможет
    # зарегистрироваться — см. purge_username_data().
    purge_username_data(username)
    print(f'[ADMIN] Deleted: {username}')
    return jsonify({'ok': True})


# ── SocketIO ─────────────────────────────────────────────────────────

@socketio.on('connect')
def on_connect():
    m = get_messenger()
    if m:
        join_room(m.username)
        with msg_buffer_lock:
            online_sockets[m.username] = online_sockets.get(m.username, 0) + 1
        emit('status', {'connected': True})
        # Flush any buffered messages from while user was offline
        flush_buffer(m.username)


@socketio.on('disconnect')
def on_disconnect():
    m = get_messenger()
    if m:
        with msg_buffer_lock:
            count = online_sockets.get(m.username, 1) - 1
            online_sockets[m.username] = max(0, count)
        update_last_seen(m.username)


# ── WebRTC Call Signaling ───────────────────────────────────────────

@socketio.on('call-offer')
def on_call_offer(data):
    """Relay WebRTC offer to the target user."""
    m = get_messenger()
    if not m:
        return
    target = data.get('to')
    if not target:
        return
    with users_lock:
        if target not in users:
            emit('call-error', {'error': f'{target} is offline'})
            return
    socketio.emit('call-offer', {
        'from': m.username,
        'offer': data.get('offer'),
        'video': data.get('video', False),
    }, room=target)


@socketio.on('call-answer')
def on_call_answer(data):
    """Relay WebRTC answer back to caller."""
    m = get_messenger()
    if not m:
        return
    target = data.get('to')
    if target:
        socketio.emit('call-answer', {
            'from': m.username,
            'answer': data.get('answer'),
        }, room=target)


@socketio.on('ice-candidate')
def on_ice_candidate(data):
    """Relay ICE candidate to peer."""
    m = get_messenger()
    if not m:
        return
    target = data.get('to')
    if target:
        socketio.emit('ice-candidate', {
            'from': m.username,
            'candidate': data.get('candidate'),
        }, room=target)


@socketio.on('call-end')
def on_call_end(data):
    """Notify peer that call ended."""
    m = get_messenger()
    if not m:
        return
    target = data.get('to')
    if target:
        socketio.emit('call-end', {'from': m.username}, room=target)


@socketio.on('read')
def on_read(data):
    """Relay read receipt to the message author."""
    m = get_messenger()
    if not m:
        return
    target = data.get('to')
    if target:
        socketio.emit('read', {'from': m.username}, room=target)


@socketio.on('typing')
def on_typing(data):
    """Relay typing indicator to peer or group room."""
    m = get_messenger()
    if not m:
        return
    target = data.get('to')
    is_group = bool(data.get('group'))
    typing = bool(data.get('typing'))
    if not target:
        return
    payload = {'from': m.username, 'typing': typing, 'group': is_group, 'chat': target}
    if is_group:
        # Group rooms are not maintained server-side; broadcast to group members
        try:
            members = m.group_members(target) if hasattr(m, 'group_members') else []
        except Exception:
            members = []
        for user in members:
            if user and user != m.username:
                socketio.emit('typing', payload, room=user)
    else:
        socketio.emit('typing', payload, room=target)


@socketio.on('call-reject')
def on_call_reject(data):
    """Notify caller that call was rejected."""
    m = get_messenger()
    if not m:
        return
    target = data.get('to')
    reason = data.get('reason', 'rejected')
    if target:
        socketio.emit('call-reject', {
            'from': m.username,
            'reason': reason,
        }, room=target)


# ═══════════════════════════════════════════════════════════════════════
# SSL — автогенерация самоподписанного сертификата
# ═══════════════════════════════════════════════════════════════════════

def ensure_ssl_cert(cert_path: str = '.messenger_cert.pem', key_path: str = '.messenger_key.pem'):
    """Генерирует самоподписанный SSL-сертификат если его нет."""
    import ssl
    import datetime

    if Path(cert_path).exists() and Path(key_path).exists():
        return cert_path, key_path

    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, 'DNS Messenger'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'DNS Tunnel'),
        ])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName('localhost'),
                    x509.IPAddress(ipaddress.IPv4Address('127.0.0.1')),
                    x509.IPAddress(ipaddress.IPv4Address('192.168.0.79')),
                ]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )

        Path(key_path).write_bytes(
            key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption())
        )
        try:
            os.chmod(key_path, 0o600)   # TLS-приватник — только владельцу
        except OSError:
            pass
        Path(cert_path).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        print(f'[+] SSL certificate generated: {cert_path}')
        return cert_path, key_path

    except ImportError:
        # Fallback: use openssl command
        import subprocess
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
            '-keyout', key_path, '-out', cert_path,
            '-days', '365', '-nodes',
            '-subj', '/CN=DNS Messenger/O=DNS Tunnel',
        ], check=True, capture_output=True)
        print(f'[+] SSL certificate generated (openssl): {cert_path}')
        return cert_path, key_path


# ═══════════════════════════════════════════════════════════════════════
# Запуск
# ═══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import argparse

    ap = argparse.ArgumentParser(description='DNS Messenger Web')
    ap.add_argument('--server',   default='127.0.0.1', help='IP relay-сервера')
    ap.add_argument('--port',     type=int, default=5353, help='Порт relay')
    ap.add_argument('--domain',   default='msg.tunnel.local')
    ap.add_argument('--web-port', type=int, default=8080)
    ap.add_argument('--doh',      default='')
    ap.add_argument('--no-ssl',   action='store_true', help='Disable HTTPS')
    args = ap.parse_args()

    server_ip = args.server
    server_port = args.port

    init_admin()

    transports = [UDPTransport(args.server, args.port, args.domain)]
    if args.doh:
        transports.append(DoHTransport(args.domain, args.doh))
    transport = MultiTransport(transports) if len(transports) > 1 else transports[0]

    ssl_ctx = None
    proto = 'http'
    if not args.no_ssl:
        try:
            import ssl
            cert, key = ensure_ssl_cert()
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_ctx.load_cert_chain(cert, key)
            proto = 'https'
        except Exception as e:
            print(f'[!] SSL setup failed ({e}), falling back to HTTP')
            print('[!] Calls & voice messages will NOT work from phone (requires HTTPS)')

    print(f'[*] Relay: {args.server}:{args.port}')
    print(f'[*] Open {proto}://localhost:{args.web_port}')
    if proto == 'https':
        print(f'[*] Phone: {proto}://192.168.0.79:{args.web_port} (accept self-signed cert)')
    print(f'[*] Admin: {proto}://localhost:{args.web_port}/admin')

    # По умолчанию слушаем ТОЛЬКО loopback: за Caddy это правильно (наружу
    # ходит прокси с TLS+заголовками). Прямой bind на 0.0.0.0 отдавал бы
    # приложение на :8080 в обход Caddy — открытый HTTP с паролем и без
    # security-заголовков. Для доступа с телефона по LAN — BIND_HOST=0.0.0.0.
    bind_host = os.environ.get('BIND_HOST', '127.0.0.1')
    if ssl_ctx:
        socketio.run(app, host=bind_host, port=args.web_port,
                     debug=False, allow_unsafe_werkzeug=True, ssl_context=ssl_ctx)
    else:
        socketio.run(app, host=bind_host, port=args.web_port,
                     debug=False, allow_unsafe_werkzeug=True)
