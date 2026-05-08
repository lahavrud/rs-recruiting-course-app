#!/usr/bin/env bash
# Sanity-check the deploy artifacts against the production contract.
# Run before uploading to S3 — catches stale-base merges that would
# regress the live site (e.g., HTTPS → HTTP, missing TLS materialization).
#
# Exits 0 if all assertions pass, non-zero on the first failure.
# Safe to run locally (no AWS / GitHub context required).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NGINX_CONF="${ROOT}/frontend/nginx.conf"
COMPOSE="${ROOT}/docker-compose.deploy.yml"
DEPLOY_SH="${ROOT}/scripts/deploy_ec2.sh"

fail=0

check() {
  local label="$1"; shift
  if "$@"; then
    echo "  ok    $label"
  else
    echo "  FAIL  $label"
    fail=1
  fi
}

grep_q() { grep -q -- "$@"; }
grep_qv() { ! grep -q -- "$@"; }

echo "Validating deploy artifacts under ${ROOT}"

echo "frontend/nginx.conf"
check "listens on 443 with ssl"               grep_q  'listen 443 ssl' "${NGINX_CONF}"

echo "docker-compose.deploy.yml"
check "nginx exposes 443:443"                 grep_q  '"443:443"'                       "${COMPOSE}"
check "nginx does NOT expose 80:80"           grep_qv '"80:80"'                         "${COMPOSE}"
check "nginx mounts ./frontend/tls read-only" grep_q  './frontend/tls:/etc/nginx/tls:ro' "${COMPOSE}"

echo "scripts/deploy_ec2.sh"
check "materializes TLS_CERT from /rs-recruitment/infra/" \
  grep_q '/rs-recruitment/infra/TLS_CERT' "${DEPLOY_SH}"
check "materializes TLS_KEY from /rs-recruitment/infra/" \
  grep_q '/rs-recruitment/infra/TLS_KEY' "${DEPLOY_SH}"

if [[ $fail -ne 0 ]]; then
  echo
  echo "Deploy artifacts failed sanity check — refusing to publish."
  echo "This usually means the branch is stale relative to main. Rebase and retry."
  exit 1
fi

echo
echo "All deploy-artifact assertions passed."
