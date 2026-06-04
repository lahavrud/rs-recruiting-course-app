#!/usr/bin/env bash
# Sanity-check the deploy artifacts against the production contract.
# Run before uploading to S3 — catches stale-base merges that would
# regress the live site.
#
# Architecture: CloudFront + S3 (frontend), EC2 nginx (API proxy, port 80).
# CloudFront terminates TLS — nginx runs HTTP-only internally.
#
# Exits 0 if all assertions pass, non-zero on the first failure.
# Safe to run locally (no AWS / GitHub context required).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NGINX_CONF="${ROOT}/nginx/nginx.conf"
COMPOSE="${ROOT}/docker-compose.deploy.yml"
DEPLOY_SH="${ROOT}/scripts/deploy_ec2.sh"
ALLOY_CONF="${ROOT}/alloy/config.alloy"

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

echo "nginx/nginx.conf"
check "listens on port 80 (CloudFront terminates TLS)" grep_q  'listen 80'      "${NGINX_CONF}"
check "does NOT listen on 443 (no TLS on EC2)"        grep_qv 'listen 443 ssl'  "${NGINX_CONF}"
check "proxies /api/ to upstream"                     grep_q  'location /api/'  "${NGINX_CONF}"

echo "docker-compose.deploy.yml"
check "nginx exposes 80:80"                           grep_q  '"80:80"'                                    "${COMPOSE}"
check "nginx does NOT expose 443:443"                 grep_qv '"443:443"'                                  "${COMPOSE}"
check "nginx mounts nginx.conf read-only"             grep_q  'nginx.conf:/etc/nginx/conf.d/default.conf:ro' "${COMPOSE}"
check "no TLS volume mount"                           grep_qv 'frontend/tls'                               "${COMPOSE}"
check "api image uses \${IMAGE_TAG}"                  grep_q  'rs-recruiting/api:${IMAGE_TAG}'             "${COMPOSE}"
check "no :latest image tag in compose"               grep_qv ':latest'                                    "${COMPOSE}"
check "worker keeps awslogs driver (compliance)"      grep_q  'awslogs'                                    "${COMPOSE}"
check "api has OTLP endpoint env var"                 grep_q  'OTEL_EXPORTER_OTLP_ENDPOINT'                 "${COMPOSE}"
check "grafana-alloy service present"                 grep_q  'grafana-alloy'                               "${COMPOSE}"
check "alloy port lo-only (not exposed to CloudFront)" grep_q '127.0.0.1:4317'                             "${COMPOSE}"

echo "alloy/config.alloy"
check "OTLP gRPC receiver on 4317"                    grep_q  '4317'                                       "${ALLOY_CONF}"
check "uses sys.env for API token"                    grep_q  'sys.env("GRAFANA_API_TOKEN")'               "${ALLOY_CONF}"
check "CloudWatch exporter present"                   grep_q  'prometheus.exporter.cloudwatch'             "${ALLOY_CONF}"

echo "scripts/deploy_ec2.sh"
check "fetches nginx.conf from S3"                    grep_q  '/deploy/${IMAGE_TAG}/nginx.conf'            "${DEPLOY_SH}"
check "no TLS materialization"                        grep_qv 'TLS_CERT'                                   "${DEPLOY_SH}"
check "resolves IMAGE_TAG (env or SSM CURRENT_SHA)"   grep_q  'CURRENT_SHA'                               "${DEPLOY_SH}"
check "fetches per-SHA compose from S3"               grep_q  '/deploy/${IMAGE_TAG}/docker-compose.deploy.yml' "${DEPLOY_SH}"
check "captures OLD_CURRENT for automatic rollback"   grep_q  'OLD_CURRENT'                               "${DEPLOY_SH}"
check "runs migrations BEFORE up -d (one-shot run --rm)" \
  grep_q 'run --rm --no-deps' "${DEPLOY_SH}"
put_writes() { grep -A3 'aws ssm put-parameter' "${DEPLOY_SH}" | grep -q -- "$1"; }
check "writes CURRENT_SHA on health-pass" put_writes '/rs-recruiting/infra/CURRENT_SHA'
check "writes PREV_SHA on health-pass"    put_writes '/rs-recruiting/infra/PREV_SHA'
check "polls Docker health status before declaring deploy complete" \
  grep_q 'Health.Status' "${DEPLOY_SH}"

if [[ $fail -ne 0 ]]; then
  echo
  echo "Deploy artifacts failed sanity check — refusing to publish."
  echo "This usually means the branch is stale relative to main. Rebase and retry."
  exit 1
fi

echo
echo "All deploy-artifact assertions passed."
