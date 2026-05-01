#!/bin/bash
# EC2 deploy script — fetches secrets from SSM Parameter Store, generates .env,
# then deploys. Runs as root via SSM Run Command. Uses the EC2 IAM role for all
# AWS access — no credentials are stored on the instance or in this script.
set -e

APP_DIR="/home/ec2-user/app"

# Derive account-specific values from the EC2 IAM role (no credentials needed)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com"
S3_BUCKET="rs-recruitment-${ACCOUNT_ID}"

echo "==> ECR registry: ${ECR_REGISTRY}"
echo "==> S3 bucket:    ${S3_BUCKET}"

echo "==> Fetching secrets from SSM Parameter Store"
SSM_OK=true
get_param() {
  # Returns the parameter value on stdout; exits non-zero if not found.
  # Must be called as: VAR=$(get_param NAME) || SSM_OK=false
  # (SSM_OK=false in a subshell $() would NOT propagate — use || in parent shell)
  aws ssm get-parameter --name "$1" --with-decryption \
    --query Parameter.Value --output text 2>/dev/null
}

# All params are required — deploy fails if any are missing
JWT_SECRET_KEY=$(get_param /rs-recruitment/prod/JWT_SECRET_KEY) \
  || { echo "ERROR: SSM parameter not found: JWT_SECRET_KEY" >&2; SSM_OK=false; }
DATABASE_URL=$(get_param /rs-recruitment/prod/DATABASE_URL) \
  || { echo "ERROR: SSM parameter not found: DATABASE_URL" >&2; SSM_OK=false; }
ALLOWED_ORIGINS=$(get_param /rs-recruitment/prod/ALLOWED_ORIGINS) \
  || { echo "ERROR: SSM parameter not found: ALLOWED_ORIGINS" >&2; SSM_OK=false; }
AWS_SES_FROM_EMAIL=$(get_param /rs-recruitment/prod/AWS_SES_FROM_EMAIL) \
  || { echo "ERROR: SSM parameter not found: AWS_SES_FROM_EMAIL" >&2; SSM_OK=false; }
EMAIL_PROVIDER=$(get_param /rs-recruitment/prod/EMAIL_PROVIDER) \
  || { echo "ERROR: SSM parameter not found: EMAIL_PROVIDER" >&2; SSM_OK=false; }
REDIS_URL=$(get_param /rs-recruitment/prod/REDIS_URL) \
  || { echo "ERROR: SSM parameter not found: REDIS_URL" >&2; SSM_OK=false; }
AWS_REGION=$(get_param /rs-recruitment/prod/AWS_REGION) \
  || { echo "ERROR: SSM parameter not found: AWS_REGION" >&2; SSM_OK=false; }
AWS_S3_BUCKET_NAME=$(get_param /rs-recruitment/prod/AWS_S3_BUCKET_NAME) \
  || { echo "ERROR: SSM parameter not found: AWS_S3_BUCKET_NAME" >&2; SSM_OK=false; }
STORAGE_PROVIDER=$(get_param /rs-recruitment/prod/STORAGE_PROVIDER) \
  || { echo "ERROR: SSM parameter not found: STORAGE_PROVIDER" >&2; SSM_OK=false; }

if [ "$SSM_OK" = "false" ]; then
  echo "ERROR: One or more required SSM parameters are missing — cannot deploy" >&2
  exit 1
fi

echo "==> Writing .env from SSM"
mkdir -p "${APP_DIR}"
# Use printf to safely handle values that contain special shell characters
printf 'JWT_SECRET_KEY=%s\n'       "${JWT_SECRET_KEY}"       >  "${APP_DIR}/.env"
printf 'DATABASE_URL=%s\n'         "${DATABASE_URL}"          >> "${APP_DIR}/.env"
printf 'ALLOWED_ORIGINS=%s\n'      "${ALLOWED_ORIGINS}"       >> "${APP_DIR}/.env"
printf 'AWS_SES_FROM_EMAIL=%s\n'   "${AWS_SES_FROM_EMAIL}"    >> "${APP_DIR}/.env"
printf 'EMAIL_PROVIDER=%s\n'       "${EMAIL_PROVIDER}"        >> "${APP_DIR}/.env"
printf 'REDIS_URL=%s\n'            "${REDIS_URL}"             >> "${APP_DIR}/.env"
printf 'AWS_REGION=%s\n'           "${AWS_REGION}"            >> "${APP_DIR}/.env"
printf 'AWS_S3_BUCKET_NAME=%s\n'   "${AWS_S3_BUCKET_NAME}"    >> "${APP_DIR}/.env"
printf 'STORAGE_PROVIDER=%s\n'     "${STORAGE_PROVIDER}"      >> "${APP_DIR}/.env"
printf 'ENVIRONMENT=%s\n'          "production"               >> "${APP_DIR}/.env"
chmod 600 "${APP_DIR}/.env"

echo "==> Logging in to ECR"
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo "==> Pulling deploy config from S3"
aws s3 cp "s3://${S3_BUCKET}/deploy/docker-compose.deploy.yml" "${APP_DIR}/docker-compose.deploy.yml"
aws s3 cp "s3://${S3_BUCKET}/deploy/nginx.conf" "${APP_DIR}/frontend/nginx.conf"

echo "==> Syncing frontend files"
# Force-copy index.html — aws s3 sync skips same-size files even when content changes
aws s3 cp "s3://${S3_BUCKET}/deploy/dist/index.html" "${APP_DIR}/frontend/dist/index.html"
aws s3 sync "s3://${S3_BUCKET}/deploy/dist/" "${APP_DIR}/frontend/dist/" --delete

echo "==> Pulling Docker images"
ECR_REGISTRY="${ECR_REGISTRY}" docker compose -f "${APP_DIR}/docker-compose.deploy.yml" pull

echo "==> Starting services"
ECR_REGISTRY="${ECR_REGISTRY}" docker compose -f "${APP_DIR}/docker-compose.deploy.yml" up -d

echo "==> Running database migrations"
docker compose -f "${APP_DIR}/docker-compose.deploy.yml" exec -T api uv run alembic upgrade head

echo "==> Deploy complete"
