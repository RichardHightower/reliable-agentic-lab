#!/usr/bin/env bash
# Hit /health and POST a signed issues.opened payload at the local receiver.
set -euo pipefail

HOST="${WEBHOOK_HOST:-127.0.0.1}"
PORT="${WEBHOOK_PORT:-8000}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [[ -z "${GITHUB_WEBHOOK_SECRET:-}" ]]; then
  echo "source /opt/agents/.env first" >&2
  exit 1
fi

echo "GET /health"
curl -fsS "http://${HOST}:${PORT}/health"
echo

BODY='{"action":"opened","issue":{"number":1,"title":"[T001] smoke","body":"id: T001","labels":[]}}'
SIG="$(printf '%s' "$BODY" | python3 -c "
import hashlib, hmac, os, sys
secret = os.environ['GITHUB_WEBHOOK_SECRET'].encode()
print('sha256=' + hmac.new(secret, sys.stdin.buffer.read(), hashlib.sha256).hexdigest())
")"

echo "POST /github-webhook (issues opened -> sol1_enhancer)"
curl -sS -D - -o /tmp/webhook-smoke-body.json \
  -X POST "http://${HOST}:${PORT}/github-webhook" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -H "X-GitHub-Delivery: smoke-1" \
  -H "X-Hub-Signature-256: ${SIG}" \
  --data "$BODY"
echo
echo "journal:"
cat "${WEBHOOK_JOURNAL:-$HERE/../../../../solutions/extra_credit/s_ext_1_webhook/work/last-webhook.json}"
echo
echo "print the sol1 command:"
"$HERE/call-sol1-enhancer.sh" T001 --print
