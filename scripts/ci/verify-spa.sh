#!/usr/bin/env bash
# Poll the frontend root until it serves (HTTP 200), so a redeploy fails loudly
# if CloudFront/S3 never comes back. ~200s budget (20 tries × 10s).
#
# Inputs (env):
#   DOMAIN   the public host to probe, e.g. app.example.com
set -euo pipefail

for i in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w '%{http_code}' "https://${DOMAIN}/")
  if [[ "$code" == "200" ]]; then
    echo "OK: / -> 200"
    exit 0
  fi
  echo "attempt $i: / -> $code, retrying..."
  sleep 10
done

echo "SPA still not serving after redeploy" >&2
exit 1
