"""
DNS Messenger Client (CLI) — интерактивный чат через DNS-туннель.

Запуск:
    python client.py alice --server 127.0.0.1 --port 5353

Команды:
    /send <user> <текст>        — отправить сообщение
    /chat <user>                — режим чата
    /group create <name>        — создать группу
    /group invite <grp> <user>  — пригласить
    /group send <grp> <текст>   — сообщение в группу
    /groups                     — список групп
    /back                       — выйти из режима чата
    /quit                       — выход
"""

import threading
import time
import sys
from pathlib import Path

from transport import UDPTransport, DoHTransport, MultiTransport
from protocol import (
    CMD_REGISTER, CMD_GETKEY, CMD_SEND, CMD_POLL,
    CMD_GROUP_CREATE, CMD_GROUP_INVITE, CMD_GROUP_SEND,
    CMD_GROUP_POLL, CMD_GROUP_LIST,
    MAX_LABEL_LEN, MAX_DOMAIN_LEN,
    b32encode, b32decode, chunk_string, gen_msg_id,
)
from crypto_utils import (
    Identity, encrypt, decrypt,
    generate_group_key, seal_group_key, unseal_group_key,
)


class Messenger:
    def __init__(self, username: str, transport):
        self.username = username
        self.transport = transport
        self.running = False
        self.chat_with: str | None = None

        data_dir = Path(f'.messenger_{username}')
        data_dir.mkdir(exist_ok=True)
        key_file = data_dir / 'identity.key'
        self.identity = Identity.load(str(key_file)) if key_file.exists() else Identity()
        if not key_file.exists():
            self.identity.save(str(key_file))

        self.peer_keys: dict[str, bytes] = {}
        self.group_keys: dict[str, bytes] = {}

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

    def send_message(self, to_user: str, text: str) -> bool:
        pk = self.get_peer_key(to_user)
        if not pk:
            print(f'  [!] Пользователь «{to_user}» не найден')
            return False
        shared = self.identity.derive_shared_key(pk)
        ct = encrypt(text.encode('utf-8'), shared)
        return self._send_chunked(CMD_SEND, [to_user, self.username], ct)

    def poll_messages(self) -> list[tuple[str, str]]:
        msgs = []
        while True:
            res = self._q([CMD_POLL, self.username, '0'])
            if res == 'EMPTY' or res.startswith('ERR'):
                break
            if res.startswith('MSG:'):
                colon = res.index(':', 4)
                fr = res[4:colon]
                data = res[colon + 1:]
                text = self._decrypt_dm(fr, data)
                msgs.append((fr, text))
        return msgs

    # ── Группы ───────────────────────────────────────────────────────

    def create_group(self, gid: str) -> bool:
        res = self._q([CMD_GROUP_CREATE, gid, self.username])
        if res.startswith('OK'):
            self.group_keys[gid] = generate_group_key()
            return True
        return False

    def invite_to_group(self, gid: str, user: str) -> bool:
        pk = self.get_peer_key(user)
        gk = self.group_keys.get(gid)
        if not pk or not gk:
            return False
        sealed = seal_group_key(gk, self.identity, pk)
        labels = [CMD_GROUP_INVITE, gid, self.username, user] + chunk_string(b32encode(sealed), MAX_LABEL_LEN)
        return self._q(labels).startswith('OK')

    def send_group_msg(self, gid: str, text: str) -> bool:
        gk = self.group_keys.get(gid)
        if not gk:
            print('  [!] Нет ключа группы')
            return False
        ct = encrypt(text.encode('utf-8'), gk)
        return self._send_chunked(CMD_GROUP_SEND, [gid, self.username], ct)

    def poll_group(self, gid: str) -> list[tuple[str, str]]:
        msgs = []
        while True:
            res = self._q([CMD_GROUP_POLL, gid, self.username])
            if res == 'EMPTY' or res.startswith('ERR'):
                break
            if res.startswith('GMSG:'):
                colon = res.index(':', 5)
                fr, data = res[5:colon], res[colon + 1:]
                gk = self.group_keys.get(gid)
                if gk:
                    try:
                        text = decrypt(b32decode(data), gk).decode('utf-8')
                    except Exception as e:
                        text = f'[ошибка: {e}]'
                else:
                    text = '[нет ключа]'
                msgs.append((fr, text))
        return msgs

    def fetch_groups(self):
        res = self._q([CMD_GROUP_LIST, self.username])
        if not res.startswith('GROUPS:'):
            return []
        groups = []
        for entry in res[7:].split('|'):
            parts = entry.split(':', 2)
            if len(parts) < 3:
                continue
            gid, key_from, key_data = parts
            groups.append(gid)
            if gid not in self.group_keys and key_data and key_from:
                spk = self.get_peer_key(key_from)
                if spk:
                    try:
                        self.group_keys[gid] = unseal_group_key(b32decode(key_data), self.identity, spk)
                    except Exception:
                        pass
        return groups

    # ── Внутренние ───────────────────────────────────────────────────

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

    def _decrypt_dm(self, sender, data_b32):
        try:
            pk = self.get_peer_key(sender)
            if not pk:
                return '[ключ не найден]'
            return decrypt(b32decode(data_b32), self.identity.derive_shared_key(pk)).decode('utf-8')
        except Exception as e:
            return f'[ошибка: {e}]'

    # ── Фоновый поллинг ──────────────────────────────────────────────

    def _poll_loop(self):
        while self.running:
            try:
                for fr, text in self.poll_messages():
                    print(f'\r  \033[1;36m[{fr}]\033[0m: {text}')
                    self._prompt()
                for gid in list(self.group_keys):
                    for fr, text in self.poll_group(gid):
                        print(f'\r  \033[1;35m[{gid}/{fr}]\033[0m: {text}')
                        self._prompt()
            except Exception:
                pass
            time.sleep(2)

    def _prompt(self):
        tag = f'{self.username}→{self.chat_with}' if self.chat_with else self.username
        print(f'  [{tag}]> ', end='', flush=True)

    # ── Интерактивный режим ──────────────────────────────────────────

    def run(self):
        print('  ╔══════════════════════════════════════╗')
        print('  ║       DNS Tunnel Messenger           ║')
        print('  ╚══════════════════════════════════════╝')
        print(f'  Пользователь : {self.username}')
        print()

        if not self.register():
            print('  [!] Регистрация не удалась')
            return
        print('  [+] Зарегистрирован')
        self.fetch_groups()

        self.running = True
        threading.Thread(target=self._poll_loop, daemon=True).start()

        print()
        print('  /send <user> <текст>         — сообщение')
        print('  /chat <user>                 — режим чата')
        print('  /group create <name>         — создать группу')
        print('  /group invite <grp> <user>   — пригласить')
        print('  /group send <grp> <текст>    — в группу')
        print('  /groups                      — список групп')
        print('  /back, /quit')
        print()

        try:
            while True:
                self._prompt()
                try:
                    line = input().strip()
                except EOFError:
                    break
                if not line:
                    continue
                if line == '/quit':
                    break
                if line.startswith('/chat '):
                    self.chat_with = line[6:].strip()
                    print(f'  [*] Чат с {self.chat_with}. /back — выход.')
                    continue
                if line == '/back':
                    self.chat_with = None
                    continue
                if line.startswith('/send '):
                    parts = line[6:].split(' ', 1)
                    if len(parts) == 2 and self.send_message(parts[0], parts[1]):
                        print(f'  \033[1;32m✓\033[0m → {parts[0]}')
                    continue
                if line.startswith('/group create '):
                    name = line[14:].strip()
                    print('  [+] Группа создана' if self.create_group(name) else '  [!] Ошибка')
                    continue
                if line.startswith('/group invite '):
                    parts = line[14:].split(' ', 1)
                    if len(parts) == 2:
                        print('  [+] Приглашён' if self.invite_to_group(parts[0], parts[1]) else '  [!] Ошибка')
                    continue
                if line.startswith('/group send '):
                    parts = line[12:].split(' ', 1)
                    if len(parts) == 2 and self.send_group_msg(parts[0], parts[1]):
                        print(f'  \033[1;32m✓\033[0m → #{parts[0]}')
                    continue
                if line == '/groups':
                    grps = self.fetch_groups()
                    print('  Группы:', ', '.join(grps) if grps else '(нет)')
                    continue
                if self.chat_with:
                    if self.send_message(self.chat_with, line):
                        print(f'  \033[1;32m✓\033[0m → {self.chat_with}')
                    continue
                print('  [?] Неизвестная команда')
        finally:
            self.running = False
            print('\n  Пока!')


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='DNS Tunnel Messenger (CLI)')
    ap.add_argument('username')
    ap.add_argument('--server', default='127.0.0.1')
    ap.add_argument('--port',   type=int, default=5353)
    ap.add_argument('--domain', default='msg.tunnel.local')
    ap.add_argument('--doh',    default='', help='DoH provider: google/yandex/cloudflare')
    args = ap.parse_args()

    transports = [UDPTransport(args.server, args.port, args.domain)]
    if args.doh:
        transports.append(DoHTransport(args.domain, args.doh))
    transport = MultiTransport(transports) if len(transports) > 1 else transports[0]

    Messenger(args.username, transport).run()
