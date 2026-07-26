"""
DNS Relay Server — ретранслятор с поддержкой групп и файлов.

Запуск:
    python server.py --domain msg.tunnel.local --port 5353
"""

import socket
import threading
import time
from collections import defaultdict

from dnslib import DNSRecord, RR, TXT, QTYPE, EDNS0

EDNS_UDP_SIZE = 4096
# Данных на один ответ скачивания. ~1400 символов + обрамление FDATA умещается
# в один UDP-пакет под типовым MTU 1500 (без IP-фрагментации), а по сравнению с
# прежними 250 режет число запросов на файл примерно в 5.6 раза.
DOWNLOAD_PIECE = 1400

from protocol import (
    CMD_REGISTER, CMD_GETKEY, CMD_SEND, CMD_POLL,
    CMD_GROUP_CREATE, CMD_GROUP_INVITE, CMD_GROUP_SEND,
    CMD_GROUP_POLL, CMD_GROUP_LIST,
    CMD_FILE_HEADER, CMD_FILE_CHUNK, CMD_FILE_POLL, CMD_FILE_DOWNLOAD,
    CMD_LIST_USERS,
    b32encode, b32decode,
)
from crypto_utils import (
    split_bundle, verify_sig,
    poll_signing_input, fpoll_signing_input, glist_signing_input,
    reg_signing_input, gpoll_signing_input, ginvite_signing_input,
)

# Бандл (X25519||Ed25519) и Ed25519-подпись — оба ровно 64 байта, значит их
# base32 одинаковой длины. Подписанная регистрация шлёт bundle_b32 + sig_b32
# без разделителя, а сервер режет строго по этой длине.
BUNDLE_LEN = 64
BUNDLE_B32_LEN = len(b32encode(bytes(BUNDLE_LEN)))
# Окно защиты poll-запроса от повтора: подписанный nonce нельзя переиспользовать
# в этом окне. Клиент шлёт свежий случайный nonce на каждый poll.
POLL_NONCE_TTL = 300.0
# Допустимый разброс между временем клиента (в подписи) и сервера. Не про
# защиту от повтора В ЭТОМ окне (то делает seen_poll_nonces) — а про то, что
# seen_poll_nonces живёт только в памяти и обнуляется рестартом релея: ts вне
# этого окна отклоняется независимо от того, помнит ли релей nonce вообще.
POLL_TS_WINDOW = 120.0

# Границы памяти релея. Хранилища наполняются НЕаутентифицированными
# отправителями (послать сообщение/файл может кто угодно), поэтому без границ
# флуд заголовками файлов (по 512 КБ) или незавершёнными чанками легко валит
# релей по памяти. Кап на вставке даёт жёсткую границу; периодический сметатель
# (_evict) добивает протухшее по TTL, даже если новых вставок нет.
ASSEMBLY_TTL = 120.0        # незавершённая сборка чанков сообщения
FILE_TTL = 3600.0           # файл — транзит; час на скачивание получателем
MAILBOX_TTL = 86400.0       # непрочитанные сообщения — сутки
MAX_MAILBOX_MSGS = 500      # очередь на одного получателя
MAX_FILES = 500             # всего файлов в памяти релея
MAX_INCOMPLETE = 1000       # одновременных незавершённых сборок (на стор)
EVICT_INTERVAL = 30.0       # не чаще раза в 30 c проходим сметателем
# Границы РАЗМЕРА одной записи (не только числа записей): total из заголовка
# контролирует атакующий, поэтому число чанков на файл/сообщение тоже надо
# ограничить, иначе один «файл» с гигантским total выест память.
MAX_MSG_CHUNKS = 1000       # чанков на одно сообщение (сообщения мелкие)
MAX_FILE_CHUNKS = 8000      # чанков на файл (512 КБ файла с запасом)
MAX_GROUPS = 5000           # групп в памяти релея
MAX_USERS = 50000           # зарегистрированных имён
STORE_TTL = 86400.0         # простаивающие группы/имена без активности — сутки

# Релей — публичный UDP-порт, отвечающий бОльшим TXT-ответом на маленький
# запрос. Source IP в UDP не проверяется НИКЕМ на сетевом уровне: атакующий
# может подделать (spoof) его как IP жертвы и получить от релея ответ,
# который тот сам, никем не приглашённый, шлёт в адрес жертвы — классическое
# DNS/UDP-усиление (amplification/reflection), релей тут неотличим от
# открытого DNS-резолвера. Так как «привязать только к localhost» тут нельзя
# (это и есть смысл релея — быть публично доступным), закрываем это response
# rate limiting (RRL) ПО ЗАЯВЛЕННОМУ источнику: ограничиваем не то, сколько
# запросов шлёт атакующий (его реальный IP в спуфинге не виден никогда), а то,
# сколько ответов релей готов направить в адрес ЛЮБОГО ОДНОГО заявленного
# адреса — так реальный DNS software (BIND/PowerDNS) и решает эту проблему.
UDP_RRL_MAX = 20            # ответов на заявленный source IP за окно
UDP_RRL_WINDOW = 5.0        # секунд
UDP_RRL_SWEEP_INTERVAL = 30.0
# Хуже всего амплификация у `u` (список всех имён) — единственная команда,
# чей ответ растёт с общим числом ПОЛЬЗОВАТЕЛЕЙ, а не с содержимым запроса.
# Обрезаем её отдельно, не только общим RRL: 24 КБ ответ на 47-байтный запрос
# при 2000 пользователях (514x) не ждёт, пока сработает лимит по частоте.
MAX_LIST_USERS_REPLY = 200


class RelayServer:
    def __init__(self, domain: str, bind: str = '0.0.0.0', port: int = 5353):
        self.domain = domain
        self.bind = bind
        self.port = port
        self.lock = threading.Lock()

        # Пользователи. Значение: {'bundle': bytes, 'pinned': bool}. pinned=True
        # означает «имя закреплено за этим ключом» (после подписанной регистрации):
        # сменить бандл или опросить ящик можно только с подписью этого ключа.
        self.users: dict[str, dict] = {}
        self.mailbox: dict[str, list] = defaultdict(list)    # user → [msg, …]
        # Виденные poll-nonce'ы для защиты от повтора: "user:nonce" → истечение.
        self.seen_poll_nonces: dict[str, float] = {}

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

        # Идемпотентность повторов: mid уже доставленных сообщений
        self.delivered_mids: dict[str, float] = {}

        # Троттлинг сметателя памяти.
        self._last_evict = time.time()

        # Response-rate-limiting по заявленному источнику UDP-пакета (см. run()).
        self._udp_hits: dict[str, list[float]] = {}
        self._last_udp_sweep = time.time()

    # ═══════════════════════════════════════════════════════════════════
    # Личные сообщения
    # ═══════════════════════════════════════════════════════════════════

    def _h_register(self, L: list[str]) -> str:
        # r.<user>.<bundle_b32>[.<sig_b32>]  — sig доказывает владение бандлом.
        if len(L) < 2:
            return 'ERR:bad_reg'
        user = L[0]
        blob = ''.join(L[1:])
        bundle_b32, sig_b32 = blob[:BUNDLE_B32_LEN], blob[BUNDLE_B32_LEN:]
        try:
            bundle = b32decode(bundle_b32)
        except Exception:
            return 'ERR:bad_reg'
        # Длину бандла НЕ навязываем: старые клиенты слали только 32-байтный
        # X25519-ключ. Такие остаются легаси-незакреплёнными (подписать нечем);
        # закрепление возможно лишь для полного 64-байтного бандла с подписью.

        # Подпись под бандлом (если прислана) проверяем Ed25519-ключом из САМОГО
        # бандла — это доказывает, что регистрант владеет приватником бандла.
        _x, ed_pub = split_bundle(bundle)
        sig_ok = False
        if sig_b32 and ed_pub:
            try:
                sig = b32decode(sig_b32)
                sig_ok = len(sig) == 64 and verify_sig(
                    ed_pub, reg_signing_input(user, bundle), sig)
            except Exception:
                sig_ok = False

        now = time.time()
        with self.lock:
            entry = self.users.get(user)
            if entry is None:
                # Новое имя. Регистрация неаутентифицированна → ограничиваем
                # число имён: при переполнении вымываем старейшее НЕзакреплённое
                # (закреплённые — реальные аккаунты, их не трогаем); если таких
                # нет — отклоняем.
                if len(self.users) >= MAX_USERS:
                    legacy = [u for u, e in self.users.items() if not e.get('pinned')]
                    if not legacy:
                        return 'ERR:full'
                    self.users.pop(min(legacy, key=lambda u: self.users[u].get('ts', 0)), None)
                self.users[user] = {'bundle': bundle, 'pinned': sig_ok, 'ts': now}
            elif entry.get('pinned'):
                # Закреплено: сменить может только владелец исходного ключа
                # (подпись верна И бандл тот же — тот же verify-ключ).
                if not (sig_ok and bundle == entry['bundle']):
                    print(f'[!] register rejected (pinned): {user}')
                    return 'ERR:pinned'
                self.users[user] = {'bundle': bundle, 'pinned': True, 'ts': now}
            else:
                # Легаси-имя (не закреплено). Апгрейд до pinned только если тот
                # же владелец обновил клиент (подпись + бандл совпадает с
                # сохранённым). Иначе — старое поведение last-write-wins, чтобы
                # атакующий чужим ключом НЕ мог закрепить чужое легаси-имя.
                pinned = bool(sig_ok and bundle == entry['bundle'])
                self.users[user] = {'bundle': bundle, 'pinned': pinned, 'ts': now}
        print(f'[+] register: {user}' + (' (pinned)' if self.users[user]['pinned'] else ''))
        return f'OK:{user}'

    def _h_getkey(self, L: list[str]) -> str:
        # KEY:<0|1 — pinned>:<bundle_b32>. pinned=1 гарантирует по построению
        # (см. _h_register), что bundle — полные 64 байта X25519||Ed25519: имя
        # закрепляется лишь после проверки подписи над ПОЛНЫМ бандлом. Клиент
        # может обнаружить несогласованный ответ (pinned=1, но бандл усечён до
        # 32 байт) — тайком понизивший до "легаси" релей, если тот честен хотя
        # бы про сам факт закрепления (см. get_peer_key).
        if not L:
            return 'ERR:no_user'
        with self.lock:
            entry = self.users.get(L[0])
        pk = entry['bundle'] if entry else None
        if not pk:
            return 'ERR:not_found'
        return f'KEY:{1 if entry.get("pinned") else 0}:{b32encode(pk)}'

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

    def _accept_poll_nonce(self, scope: str, nonce: str) -> bool:
        """Отклоняет повтор подписанного poll в окне POLL_NONCE_TTL. scope
        разделяет пространства nonce разных типов опроса (dm/file)."""
        key = f'{scope}:{nonce}'
        now = time.time()
        with self.lock:
            if len(self.seen_poll_nonces) > 10000:
                self.seen_poll_nonces = {
                    k: v for k, v in self.seen_poll_nonces.items() if v > now}
            exp = self.seen_poll_nonces.get(key)
            if exp and exp > now:
                return False
            self.seen_poll_nonces[key] = now + POLL_NONCE_TTL
            return True

    def _authorize_poll(self, user, entry, L, signing_input_fn, kind):
        """Для ЗАКРЕПЛЁННОГО имени требует валидную подпись над (user, nonce, ts)
        плюс свежий (неповторённый, недавний) nonce. Легаси-имя (не закреплено)
        проходит без подписи. Возвращает строку-ошибку или None, если запрос
        авторизован.

        Формат подписанного запроса: [user, nonce, ts, sig_b32-лейблы…]. ts —
        подписанная метка времени клиента: seen_poll_nonces живёт только в
        памяти релея, и рестарт сервера обнуляет память о уже виденных nonce —
        без ts старый перехваченный (nonce, sig) можно было бы переиграть сразу
        после рестарта. ts вне узкого окна отклоняется независимо от того,
        помнит ли релей этот nonce вообще.
        """
        if not (entry and entry.get('pinned')):
            return None
        signed_nonce, signed_ts, signed_sig = None, None, None
        if len(L) >= 4:
            try:
                sig = b32decode(''.join(L[3:]))
                if len(sig) == 64 and L[2].isdigit():
                    signed_nonce, signed_ts, signed_sig = L[1], L[2], sig
            except Exception:
                pass
        if signed_ts is None or abs(time.time() - int(signed_ts)) > POLL_TS_WINDOW:
            return 'ERR:auth'
        _x, ed_pub = split_bundle(entry['bundle'])
        if not (signed_sig and ed_pub and verify_sig(
                ed_pub, signing_input_fn(user, signed_nonce, signed_ts), signed_sig)):
            return 'ERR:auth'
        if not self._accept_poll_nonce(f'{kind}:{user}', signed_nonce):
            return 'ERR:replay'
        return None

    def _h_poll(self, L: list[str]) -> str:
        # p.<user>.0                               — легаси (без подписи)
        # p.<user>.<nonce>.<ts>.<sig_b32…>         — подписанный
        if not L:
            return 'ERR:no_user'
        user = L[0]
        with self.lock:
            entry = self.users.get(user)
        err = self._authorize_poll(user, entry, L, poll_signing_input, 'dm')
        if err:
            return err
        with self.lock:
            msgs = self.mailbox.get(user)
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
            # Создание группы неаутентифицированно — ограничиваем число групп,
            # иначе флуд `c.<rand>.x` копит записи вечно (OOM). Выкидываем
            # старейшую по активности.
            if len(self.groups) >= MAX_GROUPS:
                oldest = min(self.groups, key=lambda g: self.groups[g].get('ts', 0))
                self.groups.pop(oldest, None)
                self.group_mail.pop(oldest, None)
            self.groups[gid] = {
                'creator': creator,
                'members': {creator},
                'keys': {},
                'ts': time.time(),
            }
        print(f'[G+] group created: {gid} by {creator}')
        return f'OK:{gid}'

    def _h_ginvite(self, L: list[str]) -> str:
        # Легаси (не закреплённый inviter): i.<group>.<inviter>.<user>.<encrypted_key_labels…>
        # Подписанный (закреплённый inviter):
        #   i.<group>.<inviter>.<user>.<sig_b32 + encrypted_key_labels…>
        if len(L) < 4:
            return 'ERR:bad_ginvite'
        gid, inviter, user = L[0], L[1], L[2]
        with self.lock:
            inviter_entry = self.users.get(inviter)
        if inviter_entry and inviter_entry.get('pinned'):
            # Членство проверяется по имени (см. ниже), но раз имя закреплено за
            # ключом — требуем подпись, иначе релей мог бы приписать invite
            # ЛЮБОМУ существующему участнику, не владея его ключом, и раздуть
            # grp['members'] произвольными именами (см. crypto_utils.ginvite_signing_input).
            rest = ''.join(L[3:])
            sig_b32, enc_key_b32 = rest[:BUNDLE_B32_LEN], rest[BUNDLE_B32_LEN:]
            try:
                sig = b32decode(sig_b32)
            except Exception:
                return 'ERR:auth'
            _x, ed_pub = split_bundle(inviter_entry['bundle'])
            if not (len(sig) == 64 and ed_pub and verify_sig(
                    ed_pub, ginvite_signing_input(gid, inviter, user), sig)):
                return 'ERR:auth'
        else:
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
        # Отправитель заявлен (fr_u), не аутентифицирован — но без проверки
        # членства ЛЮБОЙ посторонний (даже незнакомый группе) мог бы флудить
        # group_mail произвольного gid. Подлинность самого содержимого/автора
        # проверяется на E2E-уровне подписью внутри шифротекста (build_signed);
        # здесь достаточно закрыть именно ресурс релея — не-член вообще не
        # проходит.
        with self.lock:
            grp = self.groups.get(gid)
            if not grp or fr_u not in grp['members']:
                return 'ERR:not_member'
        data = ''.join(L[5:])
        return self._assemble(
            mid, seq, total, data, fr_u, gid,
            self.gmsg_chunks, self.gmsg_meta, self.group_mail,
            is_group=True,
        )

    def _h_gpoll(self, L: list[str]) -> str:
        # q.<group>.<user>.0                       — легаси (без подписи)
        # q.<group>.<user>.<nonce>.<ts>.<sig_b32…> — подписанный
        if len(L) < 2:
            return 'ERR:bad_gpoll'
        gid, user = L[0], L[1]
        with self.lock:
            entry = self.users.get(user)
        # Без подписи любой мог бы отметить чужие групповые сообщения
        # прочитанными от имени 'user' (кража доставки) или преждевременно
        # выбить их из хранилища релея (readers >= members).
        err = self._authorize_poll(
            user, entry, L[1:], lambda u, n, ts: gpoll_signing_input(gid, u, n, ts), f'gpoll:{gid}')
        if err:
            return err
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
        # l.<user>                                 — легаси (без подписи)
        # l.<user>.<nonce>.<ts>.<sig_b32…>         — подписанный
        if not L:
            return 'ERR:no_user'
        user = L[0]
        with self.lock:
            entry = self.users.get(user)
        err = self._authorize_poll(user, entry, L, glist_signing_input, 'glist')
        if err:
            return err
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
        # total контролирует атакующий — ограничиваем число чанков на файл.
        if total < 1 or total > MAX_FILE_CHUNKS:
            return 'ERR:bad_total'
        with self.lock:
            # Кап числа файлов. При переполнении НЕ вымываем файл, ждущий выдачи
            # (есть указатель в file_inbox) — иначе флуд заголовками удалял бы
            # чужой недоставленный файл. Выкидываем старейший БЕЗ ожидания;
            # если таких нет — отклоняем новый заголовок.
            if fid not in self.files and len(self.files) >= MAX_FILES:
                pending = {f for fids in self.file_inbox.values() for f in fids}
                evictable = [k for k in self.files if k not in pending]
                if not evictable:
                    return 'ERR:full'
                oldest = min(evictable, key=lambda k: self.files[k].get('ts', 0))
                self.files.pop(oldest, None)
            self.files[fid] = {
                'name': name_b32, 'from': fr_u, 'to': to_u,
                'size': size, 'total': total,
                'chunks': {}, 'complete': False, 'data_b32': '',
                'ts': time.time(),
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
            if finfo['complete']:
                return 'OK:complete'      # повтор после сборки — идемпотентно
            # seq вне [0, total) отклоняем: иначе флуд разными seq раздувает
            # chunks сверх заявленного total (память).
            if seq < 0 or seq >= finfo['total']:
                return 'ERR:bad_seq'
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
        # t.<user>                                 — легаси (без подписи)
        # t.<user>.<nonce>.<ts>.<sig_b32…>         — подписанный
        if not L:
            return 'ERR:no_user'
        user = L[0]
        with self.lock:
            entry = self.users.get(user)
        err = self._authorize_poll(user, entry, L, fpoll_signing_input, 'file')
        if err:
            return err
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
        # Порция скачивания. Раньше было 250 символов «чтобы влезло в TXT», но
        # EDNS0 (4096) позволяет куда больше. DOWNLOAD_PIECE подобран так, чтобы
        # ответ FDATA укладывался в один UDP-пакет (<~1500 MTU) без фрагментации,
        # и при этом сокращал число round-trip'ов в ~5-6 раз. По DoH ограничения
        # MTU нет вовсе, так что там это тем более выигрыш.
        chunk_size = DOWNLOAD_PIECE
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
        """u — список зарегистрированных пользователей (без авторизации).

        Обрезаем до MAX_LIST_USERS_REPLY: без этого ответ растёт с ОБЩИМ
        числом пользователей, а не с чем-либо в запросе — главный вклад в
        DNS/UDP-усиление (см. UDP_RRL_* выше)."""
        with self.lock:
            user_list = list(self.users.keys())[:MAX_LIST_USERS_REPLY]
        if not user_list:
            return 'EMPTY'
        return 'USERS:' + '|'.join(user_list)

    # ═══════════════════════════════════════════════════════════════════
    # Утилиты
    # ═══════════════════════════════════════════════════════════════════

    def _rrl_allow(self, ip: str) -> bool:
        """Response-rate-limiting: не более UDP_RRL_MAX ответов на один
        заявленный source IP за UDP_RRL_WINDOW секунд. См. комментарий у
        UDP_RRL_MAX выше — это ограничивает не атакующего (его IP при
        спуфинге не виден), а объём, который релей готов направить в адрес
        любого ОДНОГО заявленного адреса, то есть ущерб для жертвы отражения."""
        now = time.time()
        with self.lock:
            if now - self._last_udp_sweep > UDP_RRL_SWEEP_INTERVAL:
                self._last_udp_sweep = now
                cutoff = now - UDP_RRL_WINDOW
                self._udp_hits = {
                    k: hits for k, hits in
                    ((k, [t for t in v if t > cutoff]) for k, v in self._udp_hits.items())
                    if hits}
            hits = self._udp_hits.setdefault(ip, [])
            cutoff = now - UDP_RRL_WINDOW
            while hits and hits[0] <= cutoff:
                hits.pop(0)
            if len(hits) >= UDP_RRL_MAX:
                return False
            hits.append(now)
            return True

    def _remember_delivered(self, mid: str):
        """Помечает mid доставленным (для идемпотентности повторов)."""
        self.delivered_mids[mid] = time.time()
        if len(self.delivered_mids) > 10000:
            # Подрезаем самые старые, чтобы множество не росло бесконечно.
            cutoff = sorted(self.delivered_mids.values())[2000]
            self.delivered_mids = {k: v for k, v in self.delivered_mids.items() if v >= cutoff}

    def _evict(self):
        """Периодически (не чаще EVICT_INTERVAL) выметает протухшее из хранилищ:
        незавершённые сборки, старые файлы, устаревшие сообщения. Инлайновые капы
        держат жёсткую границу и без этого; сметатель убирает то, что просто
        протухло без новых вставок."""
        now = time.time()
        with self.lock:
            if now - self._last_evict < EVICT_INTERVAL:
                return
            self._last_evict = now

            # 1. Незавершённые сборки сообщений/групп — по TTL.
            for chunks_store, meta_store in ((self.msg_chunks, self.msg_meta),
                                             (self.gmsg_chunks, self.gmsg_meta)):
                stale = [mid for mid, m in meta_store.items()
                         if now - (m[3] if len(m) > 3 else 0) > ASSEMBLY_TTL]
                for mid in stale:
                    chunks_store.pop(mid, None)
                    meta_store.pop(mid, None)

            # 2. Файлы — по TTL (транзит, давно должны были скачать).
            stale_f = [fid for fid, f in self.files.items()
                       if now - f.get('ts', 0) > FILE_TTL]
            for fid in stale_f:
                self.files.pop(fid, None)
            # Указатели в file_inbox на исчезнувшие файлы — вычищаем.
            for user in list(self.file_inbox):
                self.file_inbox[user] = [f for f in self.file_inbox[user] if f in self.files]
                if not self.file_inbox[user]:
                    del self.file_inbox[user]

            # 3. Почтовые ящики — TTL на сообщения + кап длины.
            for user in list(self.mailbox):
                kept = [m for m in self.mailbox[user]
                        if now - m.get('ts', now) < MAILBOX_TTL]
                if len(kept) > MAX_MAILBOX_MSGS:
                    kept = kept[-MAX_MAILBOX_MSGS:]
                if kept:
                    self.mailbox[user] = kept
                else:
                    del self.mailbox[user]

    def _assemble(self, mid, seq, total, data_b32, fr_u, dest,
                  chunks_store, meta_store, mail_store, is_group=False):
        """Собирает чанки сообщения и кладёт в почтовый ящик.

        Идемпотентно по mid: клиент повторяет чанк при потере ACK-пакета, и без
        дедупликации повтор последнего чанка одночанкового сообщения породил бы
        дубликат в ящике. Уже доставленный mid просто повторно квитируется.
        """
        # total контролирует отправитель — ограничиваем число чанков и seq.
        if total < 1 or total > MAX_MSG_CHUNKS or seq < 0 or seq >= total:
            return 'ERR:bad_chunk'
        # Идемпотентность и защита от инъекции — по (отправитель, mid), а не по
        # одному mid: чужой отправитель не может пометить mid доставленным
        # (pre-delivery drop) или влезть в чужую сборку.
        dkey = f'{fr_u}:{mid}'
        with self.lock:
            if dkey in self.delivered_mids:
                return 'OK:delivered'
            existing = meta_store.get(mid)
            if existing is None:
                if len(chunks_store) >= MAX_INCOMPLETE:
                    oldest = min(meta_store, key=lambda m: meta_store[m][3])
                    chunks_store.pop(oldest, None)
                    meta_store.pop(oldest, None)
                chunks_store[mid] = {}
                meta_store[mid] = (dest, total, fr_u, time.time())
            elif (existing[0], existing[1], existing[2]) != (dest, total, fr_u):
                # Тот же mid, но другой отправитель/адрес/total — попытка
                # инъекции чанка в чужую сборку. Не смешиваем.
                return 'ERR:mid_conflict'
            chunks_store[mid][seq] = data_b32

            if len(chunks_store[mid]) == total:
                full = ''.join(chunks_store[mid][i] for i in range(total))
                meta = meta_store[mid]
                encrypted = b32decode(full)
                box = mail_store[meta[0]]
                box.append({
                    'from': meta[2],
                    'data': b32encode(encrypted),
                    'ts': int(time.time()),
                    'id': mid,
                })
                # Кап очереди получателя: держим свежие MAX_MAILBOX_MSGS.
                if len(box) > MAX_MAILBOX_MSGS:
                    del box[:len(box) - MAX_MAILBOX_MSGS]
                del chunks_store[mid]
                del meta_store[mid]
                self._remember_delivered(dkey)
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
        self._evict()          # троттлится внутри — дёшево звать на каждый запрос
        request = DNSRecord.parse(raw)
        qname = str(request.q.qname).rstrip('.')

        if not qname.endswith(self.domain):
            return request.reply().pack()

        prefix = qname[:-(len(self.domain) + 1)]
        labels = prefix.split('.')

        # Клиент ставит случайный nonce первым лейблом (анти-кэш). Команды —
        # всегда одиночные символы из DISPATCH, а nonce им не равен, поэтому,
        # если первый лейбл не команда, это nonce — срезаем. Старый CLI без
        # nonce при этом продолжает работать (первый лейбл сразу команда).
        if labels and labels[0] not in self.DISPATCH and len(labels) > 1:
            labels = labels[1:]
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
        # Отвечаем EDNS0, чтобы резолверы знали: сервер понимает большой буфер
        # и не обязан резать ответ до 512 байт.
        reply.add_ar(EDNS0(udp_len=EDNS_UDP_SIZE))
        return reply.pack()

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.bind, self.port))
        print(f'[*] DNS Relay on {self.bind}:{self.port}  domain={self.domain}')
        print(f'[*] Ожидание подключений…')

        while True:
            data, addr = sock.recvfrom(4096)
            # RRL до разбора запроса: заявленный source IP (addr[0]) в UDP
            # ничем не проверяется и легко подделывается — сверх лимита просто
            # молчим (ни ответа, ни ошибки: сама ошибка — тоже усиление).
            if not self._rrl_allow(addr[0]):
                continue
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
