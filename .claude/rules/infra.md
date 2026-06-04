# AWS & Infrastructure Rules

## Auth model
CI/CD uses OIDC — there are no stored AWS credentials anywhere in this repo. Never add `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` to GitHub secrets, `.env`, or any config file.

## Secrets
All secrets live in SSM Parameter Store as SecureStrings. To read a parameter locally:
```bash
aws ssm get-parameter --name "/rs-recruiting/<param>" --with-decryption
```
Never hardcode a value that should be in SSM. Never commit `.env` files that contain real credentials.

## Production safety
- Never run `alembic upgrade head` directly against the production database
- Never SSH into the EC2 instance and run commands manually — use SSM Run Command
- The deploy workflow (`deploy.yml`) is the only sanctioned path to production

## CI workflows (`.github/workflows/`)
- `ci.yml` — lint, test, docker-build (change-aware: docs-only PRs skip backend)
- `deploy.yml` — build ECR image + SSM deploy. Supports manual re-deploy by SHA.
- `security-audit.yml` — weekly pip-audit for CVEs

When editing workflows:
- Preserve the `detect-changes` job — it prevents unnecessary rebuilds
- OIDC permissions block must stay on any job that calls AWS (`id-token: write`, `contents: read`)
- Poll SSM run-command status after dispatch — never fire-and-forget

## CD gate — PRs that must not trigger a deploy

`deploy.yml` runs on every merge to `main`. For PRs that touch only docs/config and should not trigger a production deploy, add a path filter exclusion to `deploy.yml`'s `on.push.paths` (or `paths-ignore`) **before merging**.

Changes that never justify a deploy:
- `CLAUDE.md`, `.claude/`, `docs/`, `*.md` (documentation)
- `.github/` files that only affect CI meta (workflow comments, issue templates, PR template)
- `scripts/validate_deploy_artifacts.sh` (runs pre-deploy, not in the image)

If you open a PR that falls into this category, either:
1. Confirm `deploy.yml` already has a `paths-ignore` covering the changed paths, or
2. Add the paths to `deploy.yml`'s `paths-ignore` in the same PR before merging.

## Infrastructure repo
Terraform/OpenTofu lives in a separate repo (`rs-recruiting-infra`). Do not modify infrastructure from this repo.

## Observability
- Sentry: backend DSN in SSM, frontend DSN in build args
- CloudWatch alarms → SNS `ops-alerts` topic
- Inspector2 scans ECR images on push
