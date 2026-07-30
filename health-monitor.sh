#!/usr/bin/env bash
# Monitor de salud VulnShop — lo ejecuta cron cada 15 min.
# Comprueba backend (API :8000/health) y frontend (sitio HTTPS via Caddy). Si algo
# falla tras un reintento, reinicia el/los contenedor(es) afectado(s) y lo registra.
# Motivo: el unico worker uvicorn puede quedar colgado por un read() bloqueante y
# Docker NO reinicia por estar solo "unhealthy" (incidente 2026-07-29, ~17h caido).
set -uo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

LOG=/var/log/vulnshop-health.log
DOMAIN=damnvulnerableapp.xyz
BACKEND_URL="http://127.0.0.1:8000/health"
FRONT_URL="https://${DOMAIN}/"
CURL_MAX=10

log() { echo "$(date '+%Y-%m-%dT%H:%M:%S%z') $*" >> "$LOG"; }

probe_backend() {  # 2 intentos con 5s (anti-flap ante fallo transitorio)
  local code=""
  for _ in 1 2; do
    code=$(curl -s -o /dev/null -m "$CURL_MAX" -w '%{http_code}' "$BACKEND_URL" 2>/dev/null)
    [ "$code" = "200" ] && return 0
    sleep 5
  done
  log "FAIL backend code=$code"; return 1
}

probe_front() {
  local code=""
  for _ in 1 2; do
    code=$(curl -sk -o /dev/null -m "$CURL_MAX" --resolve "${DOMAIN}:443:127.0.0.1" \
      -w '%{http_code}' "$FRONT_URL" 2>/dev/null)
    [ "$code" = "200" ] && return 0
    sleep 5
  done
  log "FAIL front code=$code"; return 1
}

restart_svc() {
  log "RESTART $1"
  if docker restart "$1" >/dev/null 2>&1; then log "RESTART $1 done"; else log "RESTART $1 ERROR"; fi
}

main() {
  # rota el log si supera 5MB
  if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG" 2>/dev/null || echo 0)" -gt 5242880 ]; then
    mv -f "$LOG" "$LOG.1"
  fi

  local b=1 f=1
  probe_backend || b=0
  if [ "$b" = 0 ]; then
    restart_svc vulnshop-backend-1; sleep 8
    if probe_backend; then log "RECOVERED backend"; else log "STILL-DOWN backend tras restart"; fi
  fi

  probe_front || f=0
  if [ "$f" = 0 ]; then
    # El front lo sirve Caddy desde el volumen frontend_dist (lo puebla el contenedor frontend).
    restart_svc vulnshop-frontend-1
    restart_svc vulnshop-caddy-1; sleep 8
    if probe_front; then log "RECOVERED front"; else log "STILL-DOWN front tras restart"; fi
  fi

  [ "$b" = 1 ] && [ "$f" = 1 ] && log "OK backend+front healthy"
}

# Lock para evitar solapamiento entre ejecuciones de cron.
exec 9>/var/lock/vulnshop-health.lock
flock -n 9 || { log "SKIP (otra ejecucion en curso)"; exit 0; }
main
