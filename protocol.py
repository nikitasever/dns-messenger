"""
Протокол DNS Messenger — кодирование команд в DNS-имена.

Формат запроса:  <cmd>.<params>.<data_labels>.domain.tld
Формат ответа:   TXT-запись с результатом.

Команды:
  Личные сообщения:
    r.<user>.<pubkey_b32>                          — регистрация
    k.<user>                                       — запрос публичного ключа
    s.<to>.<from>.<id>.<seq>.<n>.<data>            — отправка сообщения
    p.<user>.<token>                               — получение входящих

  Группы:
    c.<group>.<creator>                            — создать группу
    i.<group>.<inviter>.<user>.<enc_key>           — пригласить в группу
    g.<group>.<from>.<id>.<seq>.<n>.<data>         — сообщение в группу
    q.<group>.<user>                               — получить сообщения группы
    l.<user>                                       — список групп

  Файлы:
    h.<to>.<from>.<fid>.<name_b32>.<size>.<chunks> — заголовок файла
    f.<fid>.<seq>.<data>                           — чанк файла (загрузка)
    t.<user>                                       — проверить входящие файлы
    x.<fid>.<seq>                                  — скачать чанк файла
"""

import base64
import os
from typing import List

# ── DNS-ограничения ──────────────────────────────────────────────────
MAX_LABEL_LEN = 63
MAX_DOMAIN_LEN = 253

# ── Команды ──────────────────────────────────────────────────────────
# Личные
CMD_REGISTER = 'r'
CMD_GETKEY   = 'k'
CMD_SEND     = 's'
CMD_POLL     = 'p'

# Группы
CMD_GROUP_CREATE  = 'c'
CMD_GROUP_INVITE  = 'i'
CMD_GROUP_SEND    = 'g'
CMD_GROUP_POLL    = 'q'
CMD_GROUP_LIST    = 'l'

# Файлы
CMD_FILE_HEADER   = 'h'
CMD_FILE_CHUNK    = 'f'
CMD_FILE_POLL     = 't'
CMD_FILE_DOWNLOAD = 'x'

# Пользователи
CMD_LIST_USERS    = 'u'


# ── Кодирование ─────────────────────────────────────────────────────

def b32encode(data: bytes) -> str:
    """Байты → DNS-safe base32 (lowercase, без паддинга '=')."""
    return base64.b32encode(data).decode('ascii').lower().rstrip('=')


def b32decode(s: str) -> bytes:
    """DNS-safe base32 → байты."""
    s = s.upper()
    s += '=' * ((8 - len(s) % 8) % 8)
    return base64.b32decode(s)


def chunk_string(s: str, size: int) -> List[str]:
    """Разбивает строку на куски заданного размера."""
    return [s[i:i + size] for i in range(0, len(s), size)]


def gen_msg_id() -> str:
    """Короткий случайный ID (7 символов)."""
    return b32encode(os.urandom(4))[:7]


def data_per_query(overhead_labels: str, domain: str) -> int:
    """Сколько base32-символов данных влезает в один DNS-запрос."""
    overhead = len(overhead_labels) + len(domain) + 2  # точки
    available = MAX_DOMAIN_LEN - overhead
    n_labels = max(1, available // (MAX_LABEL_LEN + 1))
    return n_labels * MAX_LABEL_LEN
