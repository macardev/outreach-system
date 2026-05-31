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
cat > credentials.json << 'CREDEOF'
$CREDENTIALS_JSON
CREDEOF

echo "=== Setting up token.json ==="
cat > token.json << 'TOKENEOF'
$GMAIL_TOKEN_JSON
TOKENEOF

echo "=== Setting up sheets_token.json ==="
cat > sheets_token.json << 'SHEETSEOF'
$SHEETS_TOKEN_JSON
SHEETSEOF

echo "=== Setup complete ==="
ls -la .env credentials.json token.json sheets_token.json
echo "=== File sizes (should be 300+) ==="
wc -c credentials.json token.json sheets_token.json
