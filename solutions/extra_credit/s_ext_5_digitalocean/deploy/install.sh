#!/usr/bin/env bash
# Copy unit + nginx, reload. Run as root on the Droplet after bootstrap.sh.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
DOMAIN="${WEBHOOK_DOMAIN:-YOUR_DOMAIN}"

install -d /etc/systemd/system
install -m 0644 "$HERE/agent-webhook.service" /etc/systemd/system/agent-webhook.service

TMP="$(mktemp)"
sed "s/YOUR_DOMAIN/${DOMAIN}/g" "$HERE/nginx.conf" > "$TMP"
install -d /etc/nginx/sites-available /etc/nginx/sites-enabled
install -m 0644 "$TMP" /etc/nginx/sites-available/agent-webhook
rm -f "$TMP"
ln -sfn /etc/nginx/sites-available/agent-webhook /etc/nginx/sites-enabled/agent-webhook
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl daemon-reload
systemctl enable agent-webhook
systemctl restart agent-webhook
systemctl reload nginx

echo "unit: agent-webhook"
echo "nginx: /etc/nginx/sites-available/agent-webhook (server_name ${DOMAIN})"
echo "next: certbot --nginx -d ${DOMAIN}"
echo "health: curl -sS http://127.0.0.1:8000/health"
