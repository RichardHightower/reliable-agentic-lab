#!/usr/bin/env bash
# First boot on a DigitalOcean Ubuntu 24.04 Droplet. Run as root.
#   curl is not required. Clone the lab, then:
#     bash labs/extra-credit/ext_5_digitalocean/deploy/bootstrap.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root" >&2
  exit 1
fi

REPO_URL="${LAB_REPO_URL:-https://github.com/RichardHightower/reliable-agentic-lab.git}"
BRANCH="${LAB_BRANCH:-main}"
ROOT="${LAB_ROOT:-/opt/agents}"
HERE="$(cd "$(dirname "$0")" && pwd)"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git curl jq ca-certificates

if ! command -v task >/dev/null 2>&1; then
  sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b /usr/local/bin
fi

id -u agent >/dev/null 2>&1 || useradd --system --home "$ROOT" --shell /usr/sbin/nologin agent

if [[ ! -d "$ROOT/.git" ]]; then
  mkdir -p "$(dirname "$ROOT")"
  git clone --branch "$BRANCH" "$REPO_URL" "$ROOT"
else
  git -C "$ROOT" fetch --quiet
  git -C "$ROOT" checkout "$BRANCH"
  git -C "$ROOT" pull --ff-only || true
fi

python3 -m venv /opt/agent-env
/opt/agent-env/bin/pip install --upgrade pip
/opt/agent-env/bin/pip install -r "$ROOT/requirements.txt"

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/labs/extra-credit/ext_5_digitalocean/.env.example" "$ROOT/.env"
  echo "wrote $ROOT/.env from the example. Fill GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET, GITHUB_REPO, CRM_OWNER."
fi
chmod 0600 "$ROOT/.env"
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

mkdir -p "$ROOT/work" \
  "$ROOT/solutions/extra_credit/s_ext_1_webhook/work/locks"
if [[ ! -d "$ROOT/work/northwind-field-crm/.git" ]]; then
  OWNER="${CRM_OWNER:-${GITHUB_REPO%%/*}}"
  REPO="${CRM_REPO:-${GITHUB_REPO#*/}}"
  if [[ -n "$OWNER" && "$OWNER" != "your-github-username" ]]; then
    git clone "https://github.com/${OWNER}/${REPO}.git" "$ROOT/work/northwind-field-crm" || \
      echo "clone of ${OWNER}/${REPO} failed. run task clone from solutions/sol1_enhancer later."
  fi
fi

bash "$HERE/write-sol1-config.sh" || true

chown -R agent:agent "$ROOT" /opt/agent-env

bash "$HERE/install.sh"

echo
echo "bootstrap done."
echo "1. Edit $ROOT/.env"
echo "2. Point DNS at this Droplet"
echo "3. certbot --nginx -d \$WEBHOOK_DOMAIN"
echo "4. GitHub webhook URL: https://\$WEBHOOK_DOMAIN/github-webhook"
echo "5. journalctl -u agent-webhook -f"
echo "sol1 command: $HERE/call-sol1-enhancer.sh T001 --print"
