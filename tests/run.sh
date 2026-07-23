#!/usr/bin/env bash
# Run all tests. Usage: bash tests/run.sh
set -e
cd "$(dirname "$0")/.."

echo "== JS helper tests =="
node tests/test_helpers.mjs

echo
echo "== JS syntax check (app.js) =="
node -e "new Function(require('fs').readFileSync('static/app.js','utf8')); console.log('app.js: OK')"
node -e "new Function(require('fs').readFileSync('static/sw.js','utf8')); console.log('sw.js: OK')"

echo
echo "== Python transport (nonce + EDNS0) tests =="
python tests/test_transport.py

echo
echo "== Python Ed25519 auth tests =="
python tests/test_crypto_auth.py

echo
echo "== Python group impersonation integration test =="
python tests/test_group_auth.py

echo
echo "== Python delivery reliability (ACK retry) test =="
python tests/test_reliability.py

echo
echo "== Python Web Push tests =="
python tests/test_webpush.py

echo
echo "== Python endpoint smoke tests =="
python tests/test_endpoints.py

echo
echo "All tests passed."
