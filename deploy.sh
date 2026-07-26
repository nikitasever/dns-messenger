#!/usr/bin/env bash
# One-command production deploy for dns-messenger.
#
# Pulls the latest main, preserves runtime data (accounts/admin/blocked/profiles),
# reinstalls dependencies, restarts the systemd service and verifies health.
# Safe to re-run. On any failure it restores the previous code + data and restarts,
# so a broken deploy never leaves the service down on new-but-broken code.
#
# Usage:  ssh root@<server>  then:  /opt/dns-messenger/deploy.sh
set -euo pipefail

APP_DIR=/opt/dns-messenger
SERVICE=dns-messenger
HEALTH_URL=http://127.0.0.1:8080/
BRANCH=main

cd "$APP_DIR"

ts=$(date +%F-%H%M%S)
BK="/root/dnsmsg-backup-$ts"
mkdir -p "$BK"
# Runtime data lives outside git — back it up so a bad deploy is always recoverable.
cp -a .messenger_accounts.json .messenger_admin.json .messenger_blocked.json \
      .messenger_profiles.json "$BK"/ 2>/dev/null || true
echo "[*] backup -> $BK"

cur=$(git rev-parse --short HEAD 2>/dev/null || echo "")

rollback() {
  echo "[!] deploy FAILED — rolling back"
  [ -n "$cur" ] && git reset --hard "$cur" >/dev/null 2>&1 || true
  cp -af "$BK"/.messenger_accounts.json "$BK"/.messenger_admin.json \
         "$BK"/.messenger_blocked.json "$BK"/.messenger_profiles.json \
         "$APP_DIR"/ 2>/dev/null || true
  systemctl restart "$SERVICE" || true
  echo "[!] rolled back to ${cur:-previous state}; backup kept at $BK"
}
trap rollback ERR

echo "[*] fetching origin/$BRANCH"
git fetch -q origin "$BRANCH"
new=$(git rev-parse --short "origin/$BRANCH")
echo "[*] ${cur:-none} -> $new"

if [ "$cur" = "$new" ]; then
  echo "[=] already at $new — nothing to deploy"
  trap - ERR
  exit 0
fi

git reset --hard "origin/$BRANCH"
# .messenger_profiles.json is tracked in the repo; restore the live copy over it.
cp -af "$BK"/.messenger_profiles.json "$APP_DIR"/.messenger_profiles.json 2>/dev/null || true

rm -rf __pycache__
echo "[*] installing deps"
venv/bin/pip install -q -r requirements.txt

echo "[*] restarting $SERVICE"
systemctl restart "$SERVICE"
sleep 2

systemctl is-active --quiet "$SERVICE" || { echo "[!] service not active"; false; }

code=$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "$HEALTH_URL" || echo 000)
echo "[*] health: HTTP $code"
case "$code" in
  200|302) : ;;
  *) echo "[!] unexpected health code $code"; false ;;
esac

trap - ERR
echo "[✓] deploy OK: $new  (health $code)  backup: $BK"
