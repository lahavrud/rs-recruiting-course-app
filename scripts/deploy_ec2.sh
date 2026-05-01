#!/bin/bash
# EC2 deploy script — fetches secrets from SSM Parameter Store, generates .env,
# then deploys. Runs as root via SSM Run Command. Uses the EC2 IAM role for all
# AWS access — no credentials are stored on the instance or in this script.
#
# SSM fallback: if parameters are not yet in SSM, the existing .env is used so
# deploys continue working during the SSM migration window.
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
  local val
  if val=$(aws ssm get-parameter --name "$1" --with-decryption \
             --query Parameter.Value --output text 2>/dev/null); then
    printf '%s' "$val"
  else
    echo "WARNING: SSM parameter not found: $1" >&2
    SSM_OK=false
  fi
}

JWT_SECRET_KEY=$(get_param /rs-recruitment/prod/jwt_secret_key)
DATABASE_URL=$(get_param /rs-recruitment/prod/database_url)
ALLOWED_ORIGINS=$(get_param /rs-recruitment/prod/allowed_origins)
AWS_SES_FROM_EMAIL=$(get_param /rs-recruitment/prod/aws_ses_from_email)

if [ "$SSM_OK" = "true" ]; then
  echo "==> Writing .env from SSM"
  mkdir -p "${APP_DIR}"
  # Use printf to safely handle values that contain special shell characters
  printf 'JWT_SECRET_KEY=%s\n'       "${JWT_SECRET_KEY}"     >  "${APP_DIR}/.env"
  printf 'DATABASE_URL=%s\n'         "${DATABASE_URL}"        >> "${APP_DIR}/.env"
  printf 'ALLOWED_ORIGINS=%s\n'      "${ALLOWED_ORIGINS}"     >> "${APP_DIR}/.env"
  printf 'AWS_SES_FROM_EMAIL=%s\n'   "${AWS_SES_FROM_EMAIL}"  >> "${APP_DIR}/.env"
  printf 'REDIS_URL=%s\n'            "redis://redis:6379/0"   >> "${APP_DIR}/.env"
  printf 'STORAGE_PROVIDER=%s\n'     "s3"                     >> "${APP_DIR}/.env"
  printf 'EMAIL_PROVIDER=%s\n'       "ses"                    >> "${APP_DIR}/.env"
  printf 'AWS_REGION=%s\n'           "us-east-1"              >> "${APP_DIR}/.env"
  printf 'AWS_S3_BUCKET_NAME=%s\n'   "${S3_BUCKET}"           >> "${APP_DIR}/.env"
  printf 'ENVIRONMENT=%s\n'          "production"             >> "${APP_DIR}/.env"
  chmod 600 "${APP_DIR}/.env"
else
  echo "==> SSM parameters not yet populated — using existing .env"
  if [ ! -f "${APP_DIR}/.env" ]; then
    echo "ERROR: No .env file and SSM params missing — cannot deploy" >&2
    exit 1
  fi
fi

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
