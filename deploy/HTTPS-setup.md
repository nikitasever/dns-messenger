# HTTPS для DNS Messenger через Caddy (reverse-proxy)

Настоящий сертификат Let's Encrypt на голый IP не выдаётся, поэтому используем
magic-DNS **sslip.io**: имя `77-110-98-222.sslip.io` автоматически резолвится в
`77.110.98.222`, и Let's Encrypt проходит проверку HTTP-01 без покупки домена.

Итог: приложение остаётся на HTTP `127.0.0.1:8080`, а снаружи открыт только
`https://77-110-98-222.sslip.io`. Заодно заработают push-уведомления (нужен
secure context) и Secure-cookie.

Все команды выполняются **на сервере 77.110.98.222** (Debian/Ubuntu; под root
или через sudo).

## 1. Обновить код приложения

```bash
cd /путь/к/dns-messenger      # каталог, куда клонирован репозиторий
git pull
```

## 2. Перезапустить приложение с флагами прокси

Приложение должно слушать localhost:8080 без своего TLS (его даёт Caddy) и
доверять заголовкам прокси. Ключевые переменные окружения:

- `TRUST_PROXY=1` — брать реальный IP клиента из `X-Forwarded-For` (для
  rate-limit и логов). Без прокси НЕ ставить.
- `SESSION_COOKIE_SECURE=1` — помечать cookie сессии как Secure.
- `SECRET_KEY=...` — необязательно; если не задать, ключ создастся один раз в
  файле `.messenger_secret` и сессии переживут перезапуск.

Пример ручного запуска (порт relay поставьте свой, по умолчанию 5353):

```bash
TRUST_PROXY=1 SESSION_COOKIE_SECURE=1 \
  python web_client.py --server 127.0.0.1 --port 5353 --web-port 8080 --no-ssl
```

> Если приложение запущено через systemd/screen/nohup — добавьте эти переменные
> в unit-файл (`Environment=`) или в строку запуска и перезапустите сервис.

## 3. Установить Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
  sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
  sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

## 4. Поставить конфиг и запустить

```bash
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile   # проверить синтаксис ДО рестарта
sudo systemctl restart caddy
sudo systemctl status caddy --no-pager      # должно быть active (running)
```

Caddy при старте сам получит сертификат (первый раз — несколько секунд).
Прогресс и ошибки видно в `journalctl -u caddy -f`.

## 5. Открыть порты

Caddy'ю нужны 80 (проверка ACME + редирект на HTTPS) и 443 (HTTPS):

```bash
sudo ufw allow 80,443/tcp        # если используется ufw
```

Порт 8080 снаружи можно закрыть — трафик идёт через Caddy на localhost.
Если стоит облачный firewall (у провайдера) — откройте 80 и 443 там же.

## 6. Проверка

```bash
curl -I https://77-110-98-222.sslip.io/         # ожидаем 200 и валидный TLS
curl -s https://77-110-98-222.sslip.io/api/push/key   # {"key":"...","ok":true}
```

Проверить, что заголовки безопасности приехали и версия сервера больше не течёт:

```bash
curl -sI https://77-110-98-222.sslip.io/ | grep -iE \
  'strict-transport|content-security|x-frame|x-content-type|referrer-policy|permissions-policy|^server'
# Ожидаем строки HSTS/CSP/X-Frame-Options/nosniff/Referrer-Policy/Permissions-Policy
# и НИ ОДНОЙ строки Server: Werkzeug/… (её срезает header_down -Server).
```

Открой в браузере **https://77-110-98-222.sslip.io** — замок должен быть
«настоящим» (без предупреждений). После этого push-уведомления при закрытой
вкладке можно включать в настройках.

> **Обязательно после первого деплоя CSP:** открой DevTools → Console и
> проверь боевые сценарии — вход, отправка сообщения, **звонок** (микрофон/
> камера + STUN/TURN), превью ссылки. Если что-то не работает и в консоли есть
> `Refused to … because it violates the … Content-Security-Policy directive`,
> посмотри, какая директива сработала, и допиши нужный источник в CSP в
> `Caddyfile` (чаще всего это `connect-src` для ICE-серверов звонков). CSP
> применяется прокси, локально его не воспроизвести — поэтому финальная проверка
> только здесь. Заголовок с `'unsafe-inline'` намеренный: в шаблонах есть
> инлайновые обработчики, поэтому CSP тут ловит внешнюю инъекцию скрипта и
> кликджекинг, а не инлайновую XSS (за неё отвечает `esc()` на клиенте).

## Замечания

- **Последний рестарт по HTTP разлогинит всех** — старый код на сервере ещё без
  персистентного `SECRET_KEY`. После обновления (шаг 1) это больше не повторится.
- **Появится настоящий домен** — направьте его A-записью на `77.110.98.222`,
  замените имя в `Caddyfile` и `sudo systemctl reload caddy`. Всё остальное без
  изменений.
- Приложение сейчас работает на встроенном сервере Werkzeug. Для заметной
  нагрузки позже стоит перейти на gunicorn+eventlet, но для текущего масштаба
  за Caddy этого достаточно.
