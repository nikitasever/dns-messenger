#!/usr/bin/env bash
# Run all tests. Usage: bash tests/run.sh
set -e
cd "$(dirname "$0")/.."

echo "== JS helper tests =="
node tests/test_helpers.mjs

echo
echo "== JS syntax check (app.js) =="
node -e "new Function(require('fs').readFileSync('static/app.js','utf8')); console.log('app.js: OK')"

echo
echo "== Python endpoint smoke tests =="
python tests/test_endpoints.py

echo
echo "All tests passed."
