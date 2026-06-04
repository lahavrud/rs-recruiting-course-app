#!/bin/bash
# EC2 deploy script — pulls SHA-pinned images, runs migrations, starts services.
#
# State model:
#   OLD_CURRENT = whatever was deployed before this run (read at top)
#   On health-pass:  PREV_SHA <- OLD_CURRENT;  CURRENT_SHA <- IMAGE_TAG
#   On health-fail:  redeploy OLD_CURRENT in place; SSM params untouched
#
# Resolution order for IMAGE_TAG:
#   1. $IMAGE_TAG already exported (CI / rollback path)
#   2. SSM /rs-recruiting/infra/CURRENT_SHA (manual rerun picks up last good)
set -euo pipefail

ENVIRONMENT="${ENVIRONMENT:-prod}"
APP_DIR="/home/ec2-user/app"
REGION="us-east-1"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
S3_BUCKET="rs-recruiting-deploy-${ENVIRONMENT}-${ACCOUNT_ID}"

OLD_CURRENT=$(aws ssm get-parameter \
  --name /rs-recruiting/infra/CURRENT_SHA \
  --query 'Parameter.Value' --output text 2>/dev/null || echo "")

if [[ -z "${IMAGE_TAG:-}" ]]; then
  echo "==> IMAGE_TAG not set; falling back to CURRENT_SHA"
  IMAGE_TAG="${OLD_CURRENT}"
fi
if [[ -z "${IMAGE_TAG}" ]]; then
  echo "ERROR: IMAGE_TAG is empty and CURRENT_SHA is unset. Cannot deploy."
  exit 1
fi
export IMAGE_TAG

echo "==> ECR registry: ${ECR_REGISTRY}"
echo "==> S3 bucket:    ${S3_BUCKET}"
echo "==> IMAGE_TAG:    ${IMAGE_TAG}"
echo "==> OLD_CURRENT:  ${OLD_CURRENT:-<none>}"

echo "==> Logging in to ECR"
aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo "==> Fetching Grafana Cloud credentials from SSM"
SSM_PREFIX="/rs-recruiting/${ENVIRONMENT}"
export GRAFANA_LOKI_URL=$(aws ssm get-parameter \
  --name "${SSM_PREFIX}/GRAFANA_LOKI_URL" \
  --query 'Parameter.Value' --output text)
export GRAFANA_LOKI_USER=$(aws ssm get-parameter \
  --name "${SSM_PREFIX}/GRAFANA_LOKI_USER" \
  --query 'Parameter.Value' --output text)
export GRAFANA_TEMPO_URL=$(aws ssm get-parameter \
  --name "${SSM_PREFIX}/GRAFANA_TEMPO_URL" \
  --query 'Parameter.Value' --output text)
export GRAFANA_TEMPO_USER=$(aws ssm get-parameter \
  --name "${SSM_PREFIX}/GRAFANA_TEMPO_USER" \
  --query 'Parameter.Value' --output text)
export GRAFANA_PROMETHEUS_URL=$(aws ssm get-parameter \
  --name "${SSM_PREFIX}/GRAFANA_PROMETHEUS_URL" \
  --query 'Parameter.Value' --output text)
export GRAFANA_PROMETHEUS_USER=$(aws ssm get-parameter \
  --name "${SSM_PREFIX}/GRAFANA_PROMETHEUS_USER" \
  --query 'Parameter.Value' --output text)
export GRAFANA_API_TOKEN=$(aws ssm get-parameter \
  --name "${SSM_PREFIX}/GRAFANA_API_TOKEN" \
  --with-decryption \
  --query 'Parameter.Value' --output text)

echo "==> Fetching SHA-pinned artifacts"
mkdir -p "${APP_DIR}" "${APP_DIR}/alloy"
COMPOSE_FILE="${APP_DIR}/docker-compose.deploy.yml"
aws s3 cp "s3://${S3_BUCKET}/deploy/${IMAGE_TAG}/docker-compose.deploy.yml" "${COMPOSE_FILE}"
aws s3 cp "s3://${S3_BUCKET}/deploy/${IMAGE_TAG}/nginx.conf" "${APP_DIR}/nginx.conf"
aws s3 cp "s3://${S3_BUCKET}/deploy/${IMAGE_TAG}/alloy/config.alloy" "${APP_DIR}/alloy/config.alloy"

echo "==> Pulling Docker images"
docker compose -f "${COMPOSE_FILE}" pull

echo "==> Validating migration chain (must be exactly one head)"
HEAD_COUNT=$(docker compose -f "${COMPOSE_FILE}" run --rm --no-deps -T api \
  alembic heads 2>&1 | grep -c "(head)" || true)
if [ "${HEAD_COUNT}" -ne 1 ]; then
  echo "ERROR: alembic reports ${HEAD_COUNT} head(s) — expected exactly 1."
  docker compose -f "${COMPOSE_FILE}" run --rm --no-deps -T api alembic heads
  exit 1
fi

echo "==> Running database migrations"
docker compose -f "${COMPOSE_FILE}" run --rm --no-deps -T api alembic upgrade head
echo "==> MIGRATIONS_APPLIED schema is now at head for IMAGE_TAG=${IMAGE_TAG}"

echo "==> Starting services"
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

echo "==> Restarting nginx (refreshes upstream API IP)"
docker compose -f "${COMPOSE_FILE}" restart nginx

echo "==> Waiting for api container to become healthy (90s)"
deadline=$(( $(date +%s) + 90 ))
healthy=false
while [[ $(date +%s) -lt $deadline ]]; do
  CONTAINER_ID=$(docker compose -f "${COMPOSE_FILE}" ps -q api 2>/dev/null || echo "")
  if [[ -n "${CONTAINER_ID}" ]]; then
    HC_STATUS=$(docker inspect --format='{{.State.Health.Status}}' "${CONTAINER_ID}" 2>/dev/null || echo "")
    case "${HC_STATUS}" in
      healthy)   healthy=true; break ;;
      unhealthy) break ;;
    esac
  fi
  sleep 5
done

if ! $healthy; then
  echo "==> Health check FAILED — rolling back to ${OLD_CURRENT:-<none>}"
  if [[ -z "${OLD_CURRENT}" ]]; then
    echo "ERROR: No OLD_CURRENT (first-ever deploy?) — cannot roll back"
    exit 1
  fi
  aws s3 cp "s3://${S3_BUCKET}/deploy/${OLD_CURRENT}/docker-compose.deploy.yml" "${COMPOSE_FILE}"
  aws s3 cp "s3://${S3_BUCKET}/deploy/${OLD_CURRENT}/nginx.conf" "${APP_DIR}/nginx.conf"
  IMAGE_TAG="${OLD_CURRENT}" docker compose -f "${COMPOSE_FILE}" pull
  IMAGE_TAG="${OLD_CURRENT}" docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans
  IMAGE_TAG="${OLD_CURRENT}" docker compose -f "${COMPOSE_FILE}" restart nginx
  echo "==> Rolled back to ${OLD_CURRENT} — deploy failed"
  exit 1
fi

if [[ -n "${OLD_CURRENT}" && "${OLD_CURRENT}" != "${IMAGE_TAG}" ]]; then
  echo "==> Updating PREV_SHA -> ${OLD_CURRENT}"
  aws ssm put-parameter \
    --name /rs-recruiting/infra/PREV_SHA \
    --value "${OLD_CURRENT}" \
    --type String --overwrite >/dev/null
fi
echo "==> Updating CURRENT_SHA -> ${IMAGE_TAG}"
aws ssm put-parameter \
  --name /rs-recruiting/infra/CURRENT_SHA \
  --value "${IMAGE_TAG}" \
  --type String --overwrite >/dev/null

echo "==> Pruning old images (keep newest 3)"
KEEP_IMAGES=3
for repo in "${ECR_REGISTRY}/rs-recruiting/api"; do
  docker images "$repo" --format '{{.CreatedAt}}|{{.Repository}}:{{.Tag}}' \
    | sort -r \
    | awk -F'|' -v keep="$KEEP_IMAGES" 'NR > keep {print $2}' \
    | xargs -r docker rmi -f \
    || true
done
docker image prune -f || true

echo "==> Deploy complete (IMAGE_TAG=${IMAGE_TAG})"
