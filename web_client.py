"""
Веб-клиент DNS Messenger — Flask + SocketIO.
Многопользовательский: каждый браузер/вкладка — свой юзер.

Запуск:
    python web_client.py --server 127.0.0.1 --port 15353
    # Откройте http://localhost:8080 — логин через браузер.
    # Вторая вкладка → другой ник → второй пользователь.
"""

import os
import threading
import time
import json
import random
import hashlib
import secrets
import base64
import io
import ipaddress
from pathlib import Path

from flask import (
    Flask, render_template, request, jsonify, session,
    send_file as flask_send_file, Response,
)
from flask_socketio import SocketIO, emit, join_room
from werkzeug.middleware.proxy_fix import ProxyFix

import webpush
from transport import UDPTransport, DoHTransport, MultiTransport
from protocol import (
    CMD_REGISTER, CMD_GETKEY, CMD_SEND, CMD_POLL,
    CMD_GROUP_CREATE, CMD_GROUP_INVITE, CMD_GROUP_SEND,
    CMD_GROUP_POLL, CMD_GROUP_LIST,
    CMD_FILE_HEADER, CMD_FILE_CHUNK, CMD_FILE_POLL, CMD_FILE_DOWNLOAD,
    CMD_LIST_USERS,
    MAX_LABEL_LEN, MAX_DOMAIN_LEN, NONCE_OVERHEAD,
    b32encode, b32decode, chunk_string, gen_msg_id,
)
from crypto_utils import (
    Identity, encrypt, decrypt,
    generate_group_key, seal_group_key, unseal_group_key,
    split_bundle, build_signed, open_signed,
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

# За обратным прокси (HTTPS-терминация на Caddy/nginx) реальный IP и схема
# приходят в X-Forwarded-*. Включаем доверие к ним ТОЛЬКО по TRUST_PROXY=1 —
# иначе при прямом доступе клиент мог бы подделать свой IP заголовком и обойти
# rate-limit. Один хоп прокси. remote_addr после этого = настоящий IP клиента.
if os.environ.get('TRUST_PROXY', '0') == '1':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

socketio = SocketIO(app, cors_allowed_origins='*', manage_session=False)


# ═══════════════════════════════════════════════════════════════════════
# Пароли и хранение аккаунтов
# ═══════════════════════════════════════════════════════════════════════

ACCOUNTS_FILE = Path('.messenger_accounts.json')
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


def rate_limited(key: str, max_attempts: int = 5, window_seconds: float = 60.0) -> bool:
    """Return True if `key` has exceeded max_attempts within window_seconds."""
    now = time.time()
    with _rate_limit_lock:
        hits = _rate_limit_hits.setdefault(key, [])
        hits[:] = [t for t in hits if now - t < window_seconds]
        if len(hits) >= max_attempts:
            return True
        hits.append(now)
        return False


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


class UserMessenger:
    def __init__(self, username: str, transport):
        self.username = username
        self.transport = transport
        self.running = False
        self.poll_errors = 0

        data_dir = Path(f'.messenger_{username}')
        data_dir.mkdir(exist_ok=True)
        key_file = data_dir / 'identity.key'
        self.identity = Identity.load(str(key_file)) if key_file.exists() else Identity()
        if not key_file.exists():
            self.identity.save(str(key_file))

        self.peer_keys: dict[str, bytes] = {}      # user → X25519 (для ECDH)
        self.peer_verify: dict[str, bytes] = {}    # user → Ed25519 (для подписи)
        self.group_keys: dict[str, bytes] = {}
        self.groups: dict[str, dict] = {}

        # TOFU-пиннинг: бандл ключей пира, увиденный при первом контакте.
        # Если сервер позже отдаёт другой ключ под тем же именем — это подмена
        # (подмена при регистрации / MITM), и мы её не принимаем молча.
        self._pins_file = data_dir / 'pins.json'
        self._pins: dict[str, str] = _load_json(self._pins_file)  # user → bundle_b32
        self.key_alerts: set[str] = set()          # пиры со сменившимся ключом

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
        pk = b32encode(self.identity.public_bundle())
        # Идемпотентно (перезапись ключа) — можно повторять при потере пакета.
        return self._q_reliable([CMD_REGISTER, self.username] + chunk_string(pk, MAX_LABEL_LEN)).startswith('OK')

    def _remember_peer(self, user: str, bundle: bytes) -> bytes | None:
        """Пиннит бандл пира по TOFU. Возвращает доверенный X25519 или None,
        если ключ сменился относительно закреплённого (подмена)."""
        b32 = b32encode(bundle)
        pinned = self._pins.get(user)
        if pinned is None:
            self._pins[user] = b32
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
        res = self._q_reliable([CMD_GETKEY, user])   # чтение, повтор безопасен
        if res.startswith('KEY:'):
            return self._remember_peer(user, b32decode(res[4:]))
        return None

    def peer_verify_key(self, user: str) -> bytes | None:
        if user not in self.peer_verify and user not in self.peer_keys:
            self.get_peer_key(user)   # подтягивает и пиннит бандл
        return self.peer_verify.get(user)

    def send_dm(self, to_user: str, text: str) -> dict:
        pk = self.get_peer_key(to_user)
        if not pk:
            return {'ok': False, 'error': f'User "{to_user}" not online. Must sign in first.'}
        shared = self.identity.derive_shared_key(pk)
        ctx = self.username.encode('utf-8') + b'\x00' + to_user.encode('utf-8')
        signed = build_signed(self.identity, ctx, text.encode('utf-8'))
        ct = encrypt(signed, shared)
        ok = self._send_chunked(CMD_SEND, [to_user, self.username], ct)
        return {'ok': ok, 'error': '' if ok else 'Send error'}

    def poll_dm(self) -> list[dict]:
        msgs = []
        while True:
            res = self._q([CMD_POLL, self.username, '0'])
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
        sealed = seal_group_key(gk, self.identity, pk)
        labels = [CMD_GROUP_INVITE, gid, self.username, user] + chunk_string(b32encode(sealed), MAX_LABEL_LEN)
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
            res = self._q([CMD_GROUP_POLL, gid, self.username])
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
                        if fr in self.key_alerts:
                            auth = 'key_changed'
                        text = pt.decode('utf-8')
                    except Exception as e:
                        text, auth = f'[error: {e}]', 'error'
                else:
                    text, auth = '[no key]', 'error'
                msgs.append({'type': 'group', 'group': gid, 'from': fr, 'text': text, 'auth': auth})
        return msgs

    def fetch_groups(self):
        res = self._q([CMD_GROUP_LIST, self.username])
        if not res.startswith('GROUPS:'):
            return
        for entry in res[7:].split('|'):
            parts = entry.split(':', 2)
            if len(parts) < 3:
                continue
            gid, key_from, key_data = parts
            if gid in self.group_keys or not key_data or not key_from:
                continue
            spk = self.get_peer_key(key_from)
            if spk:
                try:
                    self.group_keys[gid] = unseal_group_key(b32decode(key_data), self.identity, spk)
                except Exception:
                    pass

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

        name_b32 = b32encode(filename.encode('utf-8'))
        if self._q_reliable([CMD_FILE_HEADER, to_user, self.username, fid, name_b32, str(len(ct)), str(total)]).startswith('ERR'):
            return {'ok': False, 'error': 'Header error'}
        for seq, chunk in enumerate(chunks):
            if self._q_reliable([CMD_FILE_CHUNK, fid, str(seq)] + chunk_string(chunk, MAX_LABEL_LEN)).startswith('ERR'):
                return {'ok': False, 'error': f'Chunk error {seq}'}
        return {'ok': True, 'fid': fid}

    def poll_files(self) -> list[dict]:
        files = []
        while True:
            res = self._q([CMD_FILE_POLL, self.username])
            if res == 'EMPTY' or res.startswith('ERR'):
                break
            if res.startswith('FILE:'):
                parts = res[5:].split(':', 3)
                if len(parts) == 4:
                    fid, fr, name_b32, size = parts
                    try:
                        fname = b32decode(name_b32).decode('utf-8')
                    except Exception:
                        fname = 'unknown'
                    files.append({'fid': fid, 'from': fr, 'name': fname, 'size': int(size)})
        return files

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
            pk = self.get_peer_key(sender)
            if not pk:
                return '[key not found]', 'error'
            plain = decrypt(b32decode(data_b32), self.identity.derive_shared_key(pk))
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
    return _restore_messenger(username)


def _restore_messenger(username: str) -> UserMessenger | None:
    if username in get_blocked():
        return None          # блокировку старый cookie обходить не должен
    with users_lock:
        m = users.get(username)
        if m:
            return m         # успели создать, пока ждали лок
        try:
            m = UserMessenger(username, transport)
            if not m.register():
                return None
            users[username] = m
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
    return render_template('index.html', username=m.username)


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
        if not password or len(password) < 4:
            return jsonify({'ok': False, 'error': 'Password: minimum 4 characters'})
        if username in accounts:
            return jsonify({'ok': False, 'error': 'Username already registered'})
        h, s = _hash_password(password)
        save_account(username, h, s)
        print(f'[+] Registered: {username}')

    elif mode == 'login':
        if username not in accounts:
            return jsonify({'ok': False, 'error': 'Account not found. Register first.'})
        acc = accounts[username]
        if not _verify_password(password, acc['hash'], acc['salt']):
            return jsonify({'ok': False, 'error': 'Wrong password'})

    else:  # anonymous
        if username in accounts:
            return jsonify({'ok': False, 'error': 'This username is registered. Enter password or choose another name.'})

    with users_lock:
        m = users.get(username)
        if not m:
            try:
                m = UserMessenger(username, transport)
                if not m.register():
                    return jsonify({'ok': False, 'error': 'Relay server unavailable'})
                users[username] = m
            except Exception as e:
                return jsonify({'ok': False, 'error': str(e)})

    m.fetch_groups()
    start_poll_loop(m)
    session['username'] = username
    session['usv'] = current_user_sv(username)
    print(f'[+] Login: {username} ({mode})')
    return jsonify({'ok': True})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    username = session.pop('username', None)
    session.pop('usv', None)
    if username:
        # Bump the session-version so the cookie just cleared (and any other
        # copy of it, captured before this call) can never be replayed again.
        bump_user_sv(username)
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
    d = request.json or {}
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
    d = request.json or {}
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
    d = request.json or {}
    group = d.get('group')
    text = d.get('text')
    if not group or not text:
        return jsonify({'ok': False, 'error': 'Missing "group" or "text"'}), 400
    return jsonify({'ok': m.send_group(group, text)})


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
    # Validate: must be a data URL, max 100KB base64
    if photo and not photo.startswith('data:image/'):
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
    d = request.json or {}
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
    return Response(
        data,
        mimetype='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
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
    if len(new_pw) < 6:
        return jsonify({'ok': False, 'error': 'Minimum 6 characters'})
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

    if ssl_ctx:
        socketio.run(app, host='0.0.0.0', port=args.web_port,
                     debug=False, allow_unsafe_werkzeug=True, ssl_context=ssl_ctx)
    else:
        socketio.run(app, host='0.0.0.0', port=args.web_port,
                     debug=False, allow_unsafe_werkzeug=True)
