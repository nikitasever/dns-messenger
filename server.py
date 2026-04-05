"""
DNS Relay Server — ретранслятор с поддержкой групп и файлов.

Запуск:
    python server.py --domain msg.tunnel.local --port 5353
"""

import socket
import threading
import time
from collections import defaultdict

from dnslib import DNSRecord, RR, TXT, QTYPE

from protocol import (
    CMD_REGISTER, CMD_GETKEY, CMD_SEND, CMD_POLL,
    CMD_GROUP_CREATE, CMD_GROUP_INVITE, CMD_GROUP_SEND,
    CMD_GROUP_POLL, CMD_GROUP_LIST,
    CMD_FILE_HEADER, CMD_FILE_CHUNK, CMD_FILE_POLL, CMD_FILE_DOWNLOAD,
    CMD_LIST_USERS,
    b32encode, b32decode,
)


class RelayServer:
    def __init__(self, domain: str, bind: str = '0.0.0.0', port: int = 5353):
        self.domain = domain
        self.bind = bind
        self.port = port
        self.lock = threading.Lock()

        # Пользователи
        self.users: dict[str, bytes] = {}                    # user → pubkey
        self.mailbox: dict[str, list] = defaultdict(list)    # user → [msg, …]

        # Сборка чанков сообщений
        self.msg_chunks: dict[str, dict[int, str]] = {}
        self.msg_meta: dict[str, tuple] = {}

        # Группы
        self.groups: dict[str, dict] = {}
        # group_id → {creator, members: set, keys: {user: {data, from_user}}}
        self.group_mail: dict[str, list] = defaultdict(list)  # group → [msg, …]
        self.gmsg_chunks: dict[str, dict[int, str]] = {}
        self.gmsg_meta: dict[str, tuple] = {}

        # Файлы
        self.files: dict[str, dict] = {}
        # fid → {name, from, to, size, total, chunks: {seq: data}, complete, data_b32}
        self.file_inbox: dict[str, list] = defaultdict(list)  # user → [fid, …]

    # ═══════════════════════════════════════════════════════════════════
    # Личные сообщения
    # ═══════════════════════════════════════════════════════════════════

    def _h_register(self, L: list[str]) -> str:
        if len(L) < 2:
            return 'ERR:bad_reg'
        user = L[0]
        pk = b32decode(''.join(L[1:]))
        with self.lock:
            self.users[user] = pk
        print(f'[+] register: {user}')
        return f'OK:{user}'

    def _h_getkey(self, L: list[str]) -> str:
        if not L:
            return 'ERR:no_user'
        with self.lock:
            pk = self.users.get(L[0])
        return f'KEY:{b32encode(pk)}' if pk else 'ERR:not_found'

    def _h_send(self, L: list[str]) -> str:
        if len(L) < 6:
            return 'ERR:bad_send'
        to_u, fr_u, mid = L[0], L[1], L[2]
        seq, total = int(L[3]), int(L[4])
        data = ''.join(L[5:])
        return self._assemble(
            mid, seq, total, data, fr_u, to_u,
            self.msg_chunks, self.msg_meta, self.mailbox,
        )

    def _h_poll(self, L: list[str]) -> str:
        if not L:
            return 'ERR:no_user'
        with self.lock:
            msgs = self.mailbox.get(L[0])
            if not msgs:
                return 'EMPTY'
            msg = msgs.pop(0)
        return f'MSG:{msg["from"]}:{msg["data"]}'

    # ═══════════════════════════════════════════════════════════════════
    # Группы
    # ═══════════════════════════════════════════════════════════════════

    def _h_gcreate(self, L: list[str]) -> str:
        # c.<group>.<creator>
        if len(L) < 2:
            return 'ERR:bad_gcreate'
        gid, creator = L[0], L[1]
        with self.lock:
            if gid in self.groups:
                return 'ERR:exists'
            self.groups[gid] = {
                'creator': creator,
                'members': {creator},
                'keys': {},
            }
        print(f'[G+] group created: {gid} by {creator}')
        return f'OK:{gid}'

    def _h_ginvite(self, L: list[str]) -> str:
        # i.<group>.<inviter>.<user>.<encrypted_key_labels…>
        if len(L) < 4:
            return 'ERR:bad_ginvite'
        gid, inviter, user = L[0], L[1], L[2]
        enc_key_b32 = ''.join(L[3:])
        with self.lock:
            grp = self.groups.get(gid)
            if not grp:
                return 'ERR:no_group'
            if inviter not in grp['members']:
                return 'ERR:not_member'
            grp['members'].add(user)
            grp['keys'][user] = {'data': enc_key_b32, 'from_user': inviter}
        print(f'[G+] {inviter} invited {user} to {gid}')
        return f'OK:invited:{user}'

    def _h_gsend(self, L: list[str]) -> str:
        # g.<group>.<from>.<id>.<seq>.<total>.<data…>
        if len(L) < 6:
            return 'ERR:bad_gsend'
        gid, fr_u, mid = L[0], L[1], L[2]
        seq, total = int(L[3]), int(L[4])
        data = ''.join(L[5:])
        return self._assemble(
            mid, seq, total, data, fr_u, gid,
            self.gmsg_chunks, self.gmsg_meta, self.group_mail,
            is_group=True,
        )

    def _h_gpoll(self, L: list[str]) -> str:
        # q.<group>.<user>
        if len(L) < 2:
            return 'ERR:bad_gpoll'
        gid, user = L[0], L[1]
        with self.lock:
            grp = self.groups.get(gid)
            if not grp:
                return 'ERR:no_group'
            if user not in grp['members']:
                return 'ERR:not_member'
            msgs = self.group_mail.get(gid)
            if not msgs:
                return 'EMPTY'
            msg = msgs[0]
            # Не удаляем — групповые сообщения читают все;
            # помечаем прочитавших
            readers = msg.setdefault('_read', set())
            if user in readers:
                # Уже прочитано — ищем следующее непрочитанное
                for m in msgs:
                    if user not in m.get('_read', set()):
                        m.setdefault('_read', set()).add(user)
                        return f'GMSG:{m["from"]}:{m["data"]}'
                return 'EMPTY'
            readers.add(user)
            # Если все прочитали — удаляем
            if readers >= grp['members']:
                msgs.pop(0)
        return f'GMSG:{msg["from"]}:{msg["data"]}'

    def _h_glist(self, L: list[str]) -> str:
        # l.<user>
        if not L:
            return 'ERR:no_user'
        user = L[0]
        with self.lock:
            result = []
            for gid, grp in self.groups.items():
                if user in grp['members']:
                    enc_key = grp['keys'].get(user, {})
                    key_from = enc_key.get('from_user', '')
                    key_data = enc_key.get('data', '')
                    result.append(f'{gid}:{key_from}:{key_data}')
        if not result:
            return 'EMPTY'
        return 'GROUPS:' + '|'.join(result)

    # ═══════════════════════════════════════════════════════════════════
    # Файлы
    # ═══════════════════════════════════════════════════════════════════

    def _h_fheader(self, L: list[str]) -> str:
        # h.<to>.<from>.<fid>.<name_b32>.<size>.<total_chunks>
        if len(L) < 6:
            return 'ERR:bad_fheader'
        to_u, fr_u, fid = L[0], L[1], L[2]
        name_b32, size, total = L[3], int(L[4]), int(L[5])
        with self.lock:
            self.files[fid] = {
                'name': name_b32, 'from': fr_u, 'to': to_u,
                'size': size, 'total': total,
                'chunks': {}, 'complete': False, 'data_b32': '',
            }
        print(f'[F] file header: {fid} {fr_u}->{to_u} ({size}B, {total} chunks)')
        return f'OK:{fid}'

    def _h_fchunk(self, L: list[str]) -> str:
        # f.<fid>.<seq>.<data_labels…>
        if len(L) < 3:
            return 'ERR:bad_fchunk'
        fid, seq = L[0], int(L[1])
        data = ''.join(L[2:])
        with self.lock:
            finfo = self.files.get(fid)
            if not finfo:
                return 'ERR:no_file'
            finfo['chunks'][seq] = data
            if len(finfo['chunks']) == finfo['total']:
                finfo['data_b32'] = ''.join(finfo['chunks'][i] for i in range(finfo['total']))
                finfo['complete'] = True
                finfo['chunks'] = {}  # Освобождаем память
                self.file_inbox[finfo['to']].append(fid)
                print(f'[F] file complete: {fid}')
                return 'OK:complete'
        return f'OK:chunk:{seq}'

    def _h_fpoll(self, L: list[str]) -> str:
        # t.<user>
        if not L:
            return 'ERR:no_user'
        user = L[0]
        with self.lock:
            fids = self.file_inbox.get(user)
            if not fids:
                return 'EMPTY'
            fid = fids.pop(0)
            finfo = self.files.get(fid)
            if not finfo or not finfo['complete']:
                return 'EMPTY'
        return f'FILE:{fid}:{finfo["from"]}:{finfo["name"]}:{finfo["size"]}'

    def _h_fdownload(self, L: list[str]) -> str:
        # x.<fid>.<seq>
        if len(L) < 2:
            return 'ERR:bad_fdl'
        fid, seq = L[0], int(L[1])
        with self.lock:
            finfo = self.files.get(fid)
            if not finfo or not finfo['complete']:
                return 'ERR:no_file'
            data = finfo['data_b32']
        # Отдаём порциями по 250 символов (влезает в TXT)
        chunk_size = 250
        start = seq * chunk_size
        if start >= len(data):
            return 'EOF'
        piece = data[start:start + chunk_size]
        total_seq = (len(data) + chunk_size - 1) // chunk_size
        return f'FDATA:{seq}:{total_seq}:{piece}'

    # ═══════════════════════════════════════════════════════════════════
    # Пользователи
    # ═══════════════════════════════════════════════════════════════════

    def _h_list_users(self, L: list[str]) -> str:
        """u — список всех зарегистрированных пользователей."""
        with self.lock:
            user_list = list(self.users.keys())
        if not user_list:
            return 'EMPTY'
        return 'USERS:' + '|'.join(user_list)

    # ═══════════════════════════════════════════════════════════════════
    # Утилиты
    # ═══════════════════════════════════════════════════════════════════

    def _assemble(self, mid, seq, total, data_b32, fr_u, dest,
                  chunks_store, meta_store, mail_store, is_group=False):
        """Собирает чанки сообщения и кладёт в почтовый ящик."""
        with self.lock:
            if mid not in chunks_store:
                chunks_store[mid] = {}
                meta_store[mid] = (dest, total, fr_u)
            chunks_store[mid][seq] = data_b32

            if len(chunks_store[mid]) == total:
                full = ''.join(chunks_store[mid][i] for i in range(total))
                meta = meta_store[mid]
                encrypted = b32decode(full)
                mail_store[meta[0]].append({
                    'from': meta[2],
                    'data': b32encode(encrypted),
                    'ts': int(time.time()),
                    'id': mid,
                })
                del chunks_store[mid]
                del meta_store[mid]
                tag = 'G' if is_group else '>'
                print(f'[{tag}] {fr_u} -> {dest} ({len(encrypted)}B)')
                return 'OK:delivered'
        return f'OK:chunk:{seq}/{total}'

    # ═══════════════════════════════════════════════════════════════════
    # DNS-обёртка
    # ═══════════════════════════════════════════════════════════════════

    DISPATCH = {
        CMD_REGISTER:      '_h_register',
        CMD_GETKEY:        '_h_getkey',
        CMD_SEND:          '_h_send',
        CMD_POLL:          '_h_poll',
        CMD_GROUP_CREATE:  '_h_gcreate',
        CMD_GROUP_INVITE:  '_h_ginvite',
        CMD_GROUP_SEND:    '_h_gsend',
        CMD_GROUP_POLL:    '_h_gpoll',
        CMD_GROUP_LIST:    '_h_glist',
        CMD_FILE_HEADER:   '_h_fheader',
        CMD_FILE_CHUNK:    '_h_fchunk',
        CMD_FILE_POLL:     '_h_fpoll',
        CMD_FILE_DOWNLOAD: '_h_fdownload',
        CMD_LIST_USERS:    '_h_list_users',
    }

    def handle_query(self, raw: bytes) -> bytes:
        request = DNSRecord.parse(raw)
        qname = str(request.q.qname).rstrip('.')

        if not qname.endswith(self.domain):
            return request.reply().pack()

        prefix = qname[:-(len(self.domain) + 1)]
        labels = prefix.split('.')
        cmd = labels[0] if labels else ''

        handler = self.DISPATCH.get(cmd)
        if handler:
            try:
                txt = getattr(self, handler)(labels[1:])
            except Exception as exc:
                txt = f'ERR:{str(exc)[:80]}'
        else:
            txt = 'ERR:unknown_cmd'

        reply = request.reply()
        parts = [txt[i:i + 255] for i in range(0, len(txt), 255)]
        reply.add_answer(RR(
            request.q.qname, QTYPE.TXT,
            rdata=TXT(parts), ttl=0,
        ))
        return reply.pack()

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.bind, self.port))
        print(f'[*] DNS Relay on {self.bind}:{self.port}  domain={self.domain}')
        print(f'[*] Ожидание подключений…')

        while True:
            data, addr = sock.recvfrom(4096)
            try:
                sock.sendto(self.handle_query(data), addr)
            except Exception as exc:
                print(f'[!] {addr}: {exc}')


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='DNS Messenger Relay')
    ap.add_argument('--domain', default='msg.tunnel.local')
    ap.add_argument('--bind',   default='0.0.0.0')
    ap.add_argument('--port',   type=int, default=5353)
    args = ap.parse_args()
    RelayServer(args.domain, args.bind, args.port).run()
