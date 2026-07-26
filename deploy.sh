#!/usr/bin/env bash
#
# deploy.sh — Full auto-deploy of the VulnShop stack to a VPS.
#
# Orchestrates EVERYTHING from your local machine:
#   1. Checks SSH connectivity
#   2. Provisions the VPS (installs Docker + Compose and configures the ufw firewall)
#   3. Uploads the code (tar over ssh; no rsync required)
#   4. Brings the stack up with docker compose (build included)
#   5. Runs end-to-end sanity checks (containers, HTTPS, cert, API, ports)
#
# Idempotent: re-running it re-deploys without wiping data or re-issuing the
# certificate (persisted in the caddy_data volume, avoiding ACME rate limits).
#
# Usage:
#   ./deploy.sh
#   VPS_HOST=1.2.3.4 DOMAIN=mydomain.xyz ./deploy.sh   # override via env
#
set -euo pipefail

# --- Configuration (override via environment variables) ---
VPS_HOST="${VPS_HOST:-163.172.157.93}"
VPS_USER="${VPS_USER:-root}"
DOMAIN="${DOMAIN:-damnvulnerableapp.xyz}"
REMOTE_DIR="${REMOTE_DIR:-/opt/vulnshop}"
SSH_OPTS=(-o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Output helpers ---
c_reset=$'\033[0m'; c_cyan=$'\033[1;36m'; c_green=$'\033[1;32m'; c_red=$'\033[1;31m'; c_yellow=$'\033[1;33m'
log()  { printf '\n%s==> %s%s\n' "$c_cyan" "$*" "$c_reset"; }
ok()   { printf '%s[OK]%s   %s\n' "$c_green" "$c_reset" "$*"; }
warn() { printf '%s[WARN]%s %s\n' "$c_yellow" "$c_reset" "$*"; }
die()  { printf '%s[ERROR]%s %s\n' "$c_red" "$c_reset" "$*" >&2; exit 1; }

remote() { ssh "${SSH_OPTS[@]}" "${VPS_USER}@${VPS_HOST}" "$@"; }

# --- 0. Local preflight ---
log "Local preflight (host=$VPS_HOST domain=$DOMAIN dir=$REMOTE_DIR)"
command -v ssh  >/dev/null || die "ssh is not installed on this machine"
command -v tar  >/dev/null || die "tar is not installed on this machine"
command -v curl >/dev/null || die "curl is not installed on this machine"
[ -f "$SCRIPT_DIR/docker-compose.yml" ] || die "docker-compose.yml not found next to this script"
[ -f "$SCRIPT_DIR/.env" ] || warn ".env not found in $SCRIPT_DIR (the lab needs its secrets)"

log "Checking SSH connection"
remote 'echo ok' >/dev/null 2>&1 || die "cannot connect over SSH to ${VPS_USER}@${VPS_HOST}"
ok "SSH connects to ${VPS_USER}@${VPS_HOST}"

# --- 1. Remote provisioning: Docker + firewall ---
# Runs on the VPS. Quoted heredoc: local variables are NOT expanded.
log "Provisioning VPS (Docker + firewall)"
remote 'bash -s' <<'REMOTE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker via get.docker.com..."
  curl -fsSL https://get.docker.com | sh >/dev/null 2>&1
else
  echo "Docker already present: $(docker --version)"
fi
systemctl enable --now docker >/dev/null 2>&1 || true

if ! command -v rsync >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq rsync >/dev/null 2>&1 || true
fi

# Firewall: only 22/80/443. ALWAYS allow 22 before enabling so the SSH
# session is not lost. --force skips the interactive prompt.
if command -v ufw >/dev/null 2>&1; then
  ufw allow 22/tcp   >/dev/null
  ufw allow 80/tcp   >/dev/null
  ufw allow 443/tcp  >/dev/null
  ufw --force enable >/dev/null
  echo "ufw firewall active (22/80/443)."
else
  echo "NOTE: ufw not available; skipping host firewall."
fi
docker --version
docker compose version
REMOTE
ok "VPS provisioned"

# --- 2. Upload code (tar over ssh, no rsync dependency) ---
log "Uploading code to ${VPS_USER}@${VPS_HOST}:${REMOTE_DIR}"
# --no-xattrs: avoid macOS bsdtar emitting Apple provenance xattrs that GNU tar warns about.
tar czf - \
  --no-xattrs \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='frontend/dist' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  -C "$SCRIPT_DIR" . \
  | remote "bash -c 'mkdir -p ${REMOTE_DIR} && tar xzf - -C ${REMOTE_DIR}'"
ok "Code synced"

# --- 3. Bring the stack up ---
log "Building and starting the stack (docker compose up -d --build)"
remote "bash -c 'cd ${REMOTE_DIR} && docker compose up -d --build'"
ok "Stack up"

# --- 4. Sanity checks ---
log "Sanity checks"

# 4a. Containers: wait for all to report a running/healthy state.
printf 'Waiting for containers to become healthy'
healthy=0
for _ in $(seq 1 40); do
  # Count services NOT running (0 = all up).
  # grep -c exits 1 when the count is 0; `|| true` keeps the remote cmd from failing then.
  not_up=$(remote "bash -c 'cd ${REMOTE_DIR} && docker compose ps --format \"{{.State}}\" | grep -cv running || true'" 2>/dev/null || echo 99)
  if [ "${not_up:-99}" = "0" ]; then healthy=1; break; fi
  printf '.'; sleep 3
done
printf '\n'
if [ "$healthy" = "1" ]; then ok "All containers are running"; else warn "Some container did not reach running (check: docker compose ps)"; fi
remote "bash -c 'cd ${REMOTE_DIR} && docker compose ps --format \"table {{.Name}}\t{{.Status}}\t{{.Ports}}\"'"

# 4b. Backend health directly inside the VPS (loopback).
if remote "bash -c 'curl -fsS --max-time 10 http://localhost:8000/health >/dev/null'"; then
  ok "Backend /health responds (localhost:8000 on the VPS)"
else
  warn "Backend /health did not respond on localhost:8000"
fi

# 4c. External HTTPS + certificate (with retries: the ACME cert may take a moment).
printf 'Checking external HTTPS (https://%s)' "$DOMAIN"
https_ok=0
for _ in $(seq 1 20); do
  code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "https://${DOMAIN}/" 2>/dev/null || echo 000)
  if [ "$code" = "200" ]; then https_ok=1; break; fi
  printf '.'; sleep 6
done
printf '\n'
[ "$https_ok" = "1" ] && ok "https://${DOMAIN}/ -> HTTP 200" || warn "https://${DOMAIN}/ did not return 200 (DNS/cert still propagating?)"

# 4d. Certificate issued by Let's Encrypt.
if command -v openssl >/dev/null 2>&1; then
  issuer=$(echo | openssl s_client -servername "$DOMAIN" -connect "${DOMAIN}:443" 2>/dev/null | openssl x509 -noout -issuer 2>/dev/null || true)
  echo "$issuer" | grep -qi "let's encrypt" && ok "Certificate issued by Let's Encrypt" || warn "Could not confirm certificate issuer"
fi

# 4e. End-to-end API (Caddy -> backend -> Postgres).
if curl -sS --max-time 15 "https://${DOMAIN}/api/products" 2>/dev/null | grep -q '"products"'; then
  ok "API /api/products returns data (backend + DB OK)"
else
  warn "/api/products did not return the expected data"
fi

# 4f. HTTP -> HTTPS redirect.
rcode=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "http://${DOMAIN}/" 2>/dev/null || echo 000)
[ "$rcode" = "308" ] || [ "$rcode" = "301" ] || [ "$rcode" = "302" ] && ok "HTTP redirects to HTTPS ($rcode)" || warn "HTTP does not redirect (code $rcode)"

# 4g. Infrastructure ports closed to the internet (best-effort via nc).
if command -v nc >/dev/null 2>&1; then
  for p in 5432 6379 8000; do
    if nc -z -w5 "$VPS_HOST" "$p" 2>/dev/null; then
      warn "Port $p OPEN to the internet (should be closed)"
    else
      ok "Port $p closed to the internet"
    fi
  done
else
  warn "nc not available; skipping closed-ports check"
fi

log "Deployment complete"
printf '  URL:      https://%s\n' "$DOMAIN"
printf '  Swagger:  https://%s/api/docs\n' "$DOMAIN"
printf '  VPS dir:  %s\n' "$REMOTE_DIR"
