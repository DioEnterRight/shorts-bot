#!/usr/bin/env bash
# Starts FreeLLMAPI INSIDE this GitHub Actions job (official Docker image) from the FREELLMAPI_KEYS secret,
# reads its unified key and hands FREELLM_BASE_URL / FREELLM_API_KEY to the next steps. Same setup as roblox-stories-bot.
# No secret = the free 3D builder is off (exit 0). Anything else wrong = fail loudly with the container log.
set -euo pipefail

if [ -z "${FREELLMAPI_KEYS:-}" ]; then
  echo "::notice::FREELLMAPI_KEYS secret not set: FreeLLMAPI not started (free 3D builder off). See FREELLM_SETUP.md."
  exit 0
fi
IMAGE="${FREELLMAPI_IMAGE:-ghcr.io/tashfeenahmed/freellmapi:latest}"
PORT=3001
EMAIL="bot@example.com"
PASS="$(openssl rand -hex 16)"
export ENCRYPTION_KEY="$(openssl rand -hex 32)"

FREEAPI_CONFIG_JSON="$(EMAIL="$EMAIL" PASS="$PASS" python3 - <<'PY'
import json, os, sys
try:
    keys = json.loads(os.environ["FREELLMAPI_KEYS"])
except ValueError as e:
    sys.exit(f"FREELLMAPI_KEYS is not valid JSON: {e}")
if not isinstance(keys, list) or not keys:
    sys.exit("FREELLMAPI_KEYS must be a non-empty JSON list like [{\"platform\":\"groq\",\"key\":\"gsk_...\"}]")
for k in keys:
    if not isinstance(k, dict) or not k.get("platform") or not k.get("key"):
        sys.exit("every item in FREELLMAPI_KEYS needs a \"platform\" and a \"key\"")
print(json.dumps({"admin": {"email": os.environ["EMAIL"], "password": os.environ["PASS"]}, "keys": keys}))
PY
)"
export FREEAPI_CONFIG_JSON

docker run -d --name freellmapi -p "127.0.0.1:${PORT}:${PORT}" \
  -e ENCRYPTION_KEY -e FREEAPI_CONFIG_JSON "$IMAGE" >/dev/null

for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/ping" >/dev/null 2>&1; then break; fi
  if [ "$i" = 60 ]; then
    echo "::error::FreeLLMAPI did not start in 2 minutes. Container log:"
    docker logs freellmapi 2>&1 | tail -40
    exit 1
  fi
  sleep 2
done

TOKEN="$(curl -fsS -X POST "http://127.0.0.1:${PORT}/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')" \
  || { echo "::error::Could not log in to FreeLLMAPI"; docker logs freellmapi 2>&1 | tail -40; exit 1; }

KEY="$(curl -fsS "http://127.0.0.1:${PORT}/api/settings/api-key" -H "Authorization: Bearer $TOKEN" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["apiKey"])')" \
  || { echo "::error::Could not read the FreeLLMAPI unified key"; docker logs freellmapi 2>&1 | tail -40; exit 1; }

echo "::add-mask::$KEY"
{
  echo "FREELLM_BASE_URL=http://127.0.0.1:${PORT}/v1"
  echo "FREELLM_API_KEY=$KEY"
} >> "${GITHUB_ENV:-/dev/null}"
echo "FreeLLMAPI is running inside this job with $(python3 -c 'import json,os; print(len(json.loads(os.environ["FREELLMAPI_KEYS"])))') provider key(s)."
