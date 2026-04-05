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

from transport import UDPTransport, DoHTransport, MultiTransport
from protocol import (
    CMD_REGISTER, CMD_GETKEY, CMD_SEND, CMD_POLL,
    CMD_GROUP_CREATE, CMD_GROUP_INVITE, CMD_GROUP_SEND,
    CMD_GROUP_POLL, CMD_GROUP_LIST,
    CMD_FILE_HEADER, CMD_FILE_CHUNK, CMD_FILE_POLL, CMD_FILE_DOWNLOAD,
    CMD_LIST_USERS,
    MAX_LABEL_LEN, MAX_DOMAIN_LEN,
    b32encode, b32decode, chunk_string, gen_msg_id,
)
from crypto_utils import (
    Identity, encrypt, decrypt,
    generate_group_key, seal_group_key, unseal_group_key,
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dns-messenger-session-key')
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


def init_admin():
    """Создать файл админа если его нет."""
    if not ADMIN_FILE.exists():
        password = 'admin'  # дефолтный пароль, сменить при первом входе
        h, s = _hash_password(password)
        _save_json(ADMIN_FILE, {'hash': h, 'salt': s, 'change_required': True})
        print(f'[!] Admin password: {password} (change on first login at /admin)')


# ═══════════════════════════════════════════════════════════════════════
# Мессенджер (один инстанс на пользователя)
# ═══════════════════════════════════════════════════════════════════════

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

        self.peer_keys: dict[str, bytes] = {}
        self.group_keys: dict[str, bytes] = {}
        self.groups: dict[str, dict] = {}

    def _q(self, labels):
        return self.transport.query(labels)

    def register(self) -> bool:
        pk = b32encode(self.identity.public_bytes())
        return self._q([CMD_REGISTER, self.username] + chunk_string(pk, MAX_LABEL_LEN)).startswith('OK')

    def get_peer_key(self, user: str) -> bytes | None:
        if user in self.peer_keys:
            return self.peer_keys[user]
        res = self._q([CMD_GETKEY, user])
        if res.startswith('KEY:'):
            k = b32decode(res[4:])
            self.peer_keys[user] = k
            return k
        return None

    def send_dm(self, to_user: str, text: str) -> dict:
        pk = self.get_peer_key(to_user)
        if not pk:
            return {'ok': False, 'error': f'User "{to_user}" not online. Must sign in first.'}
        shared = self.identity.derive_shared_key(pk)
        ct = encrypt(text.encode('utf-8'), shared)
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
                msgs.append({'type': 'dm', 'from': fr, 'text': self._decrypt_from(fr, data)})
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
        return self._send_chunked(CMD_GROUP_SEND, [gid, self.username], encrypt(text.encode('utf-8'), gk))

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
                        text = decrypt(b32decode(data), gk).decode('utf-8')
                    except Exception as e:
                        text = f'[error: {e}]'
                else:
                    text = '[no key]'
                msgs.append({'type': 'group', 'group': gid, 'from': fr, 'text': text})
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

        overhead = len(f'f.{fid}.000.') + len(self.transport.domain) + 2
        avail = MAX_DOMAIN_LEN - overhead
        per_chunk = max(MAX_LABEL_LEN, (avail // (MAX_LABEL_LEN + 1)) * MAX_LABEL_LEN)
        chunks = chunk_string(ct_b32, per_chunk) if ct_b32 else ['']
        total = len(chunks)

        name_b32 = b32encode(filename.encode('utf-8'))
        if self._q([CMD_FILE_HEADER, to_user, self.username, fid, name_b32, str(len(ct)), str(total)]).startswith('ERR'):
            return {'ok': False, 'error': 'Header error'}
        for seq, chunk in enumerate(chunks):
            if self._q([CMD_FILE_CHUNK, fid, str(seq)] + chunk_string(chunk, MAX_LABEL_LEN)).startswith('ERR'):
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
        all_data, seq = '', 0
        while True:
            res = self._q([CMD_FILE_DOWNLOAD, fid, str(seq)])
            if res == 'EOF' or res.startswith('ERR'):
                break
            if res.startswith('FDATA:'):
                parts = res[6:].split(':', 2)
                if len(parts) == 3:
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
        avail = MAX_DOMAIN_LEN - len(overhead) - len(self.transport.domain) - 2
        per_q = max(MAX_LABEL_LEN, (avail // (MAX_LABEL_LEN + 1)) * MAX_LABEL_LEN)
        chunks = chunk_string(data_b32, per_q) if data_b32 else ['']
        total = len(chunks)
        for seq, chunk in enumerate(chunks):
            labels = [cmd] + prefix + [mid, str(seq), str(total)] + chunk_string(chunk, MAX_LABEL_LEN)
            if self._q(labels).startswith('ERR'):
                return False
        return True

    def _decrypt_from(self, sender, data_b32):
        try:
            pk = self.get_peer_key(sender)
            if not pk:
                return '[key not found]'
            return decrypt(b32decode(data_b32), self.identity.derive_shared_key(pk)).decode('utf-8')
        except Exception as e:
            return f'[error: {e}]'


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
    with msg_buffer_lock:
        if online_sockets.get(username, 0) > 0:
            socketio.emit(event, data, room=username)
        else:
            if username not in msg_buffer:
                msg_buffer[username] = []
            # Keep max 500 buffered messages per user
            if len(msg_buffer[username]) < 500:
                msg_buffer[username].append({'event': event, 'data': data})


def flush_buffer(username: str):
    """Send all buffered messages to user."""
    with msg_buffer_lock:
        buf = msg_buffer.pop(username, [])
    for item in buf:
        socketio.emit(item['event'], item['data'], room=username)


def get_messenger() -> UserMessenger | None:
    username = session.get('username')
    if not username:
        return None
    with users_lock:
        return users.get(username)


def start_poll_loop(m: UserMessenger):
    if m.running:
        return
    m.running = True

    def loop():
        while m.running:
            try:
                for msg in m.poll_dm():
                    buffer_or_emit('message', msg, m.username)
                for gid in list(m.group_keys):
                    for msg in m.poll_group(gid):
                        buffer_or_emit('message', msg, m.username)
                for finfo in m.poll_files():
                    buffer_or_emit('file', finfo, m.username)
                m.poll_errors = 0
                update_last_seen(m.username)
                socketio.emit('status', {'connected': True}, room=m.username)
            except Exception:
                m.poll_errors += 1
                socketio.emit('status', {'connected': False, 'errors': m.poll_errors}, room=m.username)
            time.sleep(2)

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


@app.route('/api/login', methods=['POST'])
def api_login():
    username = request.json.get('username', '').strip().lower()
    password = request.json.get('password', '').strip()
    mode = request.json.get('mode', 'anonymous')  # 'register', 'login', 'anonymous'

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
    print(f'[+] Login: {username} ({mode})')
    return jsonify({'ok': True})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    username = session.pop('username', None)
    if username:
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
    d = request.json
    return jsonify(m.send_dm(d['to'], d['text']))


@app.route('/api/resolve', methods=['POST'])
def api_resolve():
    m = get_messenger()
    if not m:
        return jsonify({'found': False, 'error': 'Not authorized'})
    user = request.json.get('user', '').strip().lower()
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
    gid = request.json.get('group', '').strip().lower()
    if not gid:
        return jsonify({'ok': False, 'error': 'Enter group name'})
    if len(gid) < 2 or len(gid) > 32:
        return jsonify({'ok': False, 'error': 'Name: 2-32 characters'})
    if not all(c.isascii() and (c.isalnum() or c == '_') for c in gid):
        return jsonify({'ok': False, 'error': 'Only latin letters, digits and _ (DNS limit)'})
    ok = m.create_group(gid)
    if not ok:
        return jsonify({'ok': False, 'error': 'Failed — group may already exist'})
    return jsonify({'ok': True})


@app.route('/api/groups/invite', methods=['POST'])
def api_group_invite():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False})
    d = request.json
    return jsonify(m.invite_to_group(d['group'], d['user']))


@app.route('/api/groups/send', methods=['POST'])
def api_group_send():
    m = get_messenger()
    if not m:
        return jsonify({'ok': False})
    d = request.json
    return jsonify({'ok': m.send_group(d['group'], d['text'])})


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

@app.route('/api/last-seen/<username>')
def api_last_seen(username):
    m = get_messenger()
    if not m:
        return jsonify({'online': False})
    with users_lock:
        is_online = username in users and users[username].running
    with last_seen_lock:
        ts = last_seen.get(username)
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
    usernames = request.json.get('users', [])
    result = {}
    with users_lock:
        online_set = {u for u, um in users.items() if um.running}
    with last_seen_lock:
        for u in usernames:
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
    photo = request.json.get('photo', '')
    # Validate: must be a data URL, max 100KB base64
    if photo and not photo.startswith('data:image/'):
        return jsonify({'ok': False, 'error': 'Invalid image format'})
    if len(photo) > 150_000:
        return jsonify({'ok': False, 'error': 'Image too large (max ~100KB)'})
    save_profile_photo(m.username, photo)
    return jsonify({'ok': True})


@app.route('/api/profile/photo/<username>')
def api_profile_photo_get(username):
    profiles = get_profiles()
    p = profiles.get(username, {})
    return jsonify({'photo': p.get('photo', '')})


@app.route('/api/profile/photos', methods=['POST'])
def api_profile_photos_batch():
    """Get photos for multiple users at once."""
    usernames = request.json.get('users', [])
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
    d = request.json
    result = m.download_file(d['fid'], d['from'])
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
    if not session.get('is_admin'):
        return render_template('admin_login.html')
    return render_template('admin.html')


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    password = request.json.get('password', '')
    admin_data = _load_json(ADMIN_FILE)
    if not admin_data:
        return jsonify({'ok': False, 'error': 'Admin not configured'})
    if not _verify_password(password, admin_data['hash'], admin_data['salt']):
        return jsonify({'ok': False, 'error': 'Wrong password'})
    session['is_admin'] = True
    return jsonify({'ok': True, 'change_required': admin_data.get('change_required', False)})


@app.route('/api/admin/change-password', methods=['POST'])
def admin_change_password():
    if not session.get('is_admin'):
        return jsonify({'ok': False, 'error': 'Not authorized'})
    new_pw = request.json.get('password', '')
    if len(new_pw) < 6:
        return jsonify({'ok': False, 'error': 'Minimum 6 characters'})
    h, s = _hash_password(new_pw)
    _save_json(ADMIN_FILE, {'hash': h, 'salt': s, 'change_required': False})
    return jsonify({'ok': True})


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('is_admin', None)
    return jsonify({'ok': True})


@app.route('/api/admin/users')
def admin_users():
    if not session.get('is_admin'):
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
    if not session.get('is_admin'):
        return jsonify({'ok': False})
    username = request.json.get('username', '')
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
    if not session.get('is_admin'):
        return jsonify({'ok': False})
    username = request.json.get('username', '')
    blocked = get_blocked()
    blocked.discard(username)
    save_blocked(blocked)
    print(f'[ADMIN] Unblocked: {username}')
    return jsonify({'ok': True})


@app.route('/api/admin/delete', methods=['POST'])
def admin_delete():
    if not session.get('is_admin'):
        return jsonify({'ok': False})
    username = request.json.get('username', '')
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
