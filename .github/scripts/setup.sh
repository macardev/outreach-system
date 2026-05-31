#!/usr/bin/env bash
set -euo pipefail

echo "=== Setting up .env ==="
cat > .env <<EOF
GOOGLE_MAPS_API_KEY="${GOOGLE_MAPS_API_KEY}"
GEMINI_API_KEY="${GEMINI_API_KEY}"
SPREADSHEET_ID="${SPREADSHEET_ID}"
SENDER_NAME="${SENDER_NAME}"
SENDER_EMAIL="${SENDER_EMAIL}"
WARMUP_START_DATE="${WARMUP_START_DATE}"
EOF

echo "=== Setting up credentials.json ==="
python3 -c "
import sys
with open('credentials.json', 'w') as f:
    f.write(sys.stdin.read())
" <<< "${CREDENTIALS_JSON}"

echo "=== Setting up token.json ==="
python3 -c "
import sys
with open('token.json', 'w') as f:
    f.write(sys.stdin.read())
" <<< "${GMAIL_TOKEN_JSON}"

echo "=== Setting up sheets_token.json ==="
python3 -c "
import sys
with open('sheets_token.json', 'w') as f:
    f.write(sys.stdin.read())
" <<< "${SHEETS_TOKEN_JSON}"

echo "=== Setup complete ==="
ls -la .env credentials.json token.json sheets_token.json
echo "=== credentials.json first 50 chars ==="
head -c 50 credentials.json
echo ""
