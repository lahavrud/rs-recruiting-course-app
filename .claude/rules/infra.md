# AWS & Infrastructure Rules

This repo ships to Kubernetes via **strict GitOps**: CI has no cluster credentials —
it builds images and commits image-tag bumps to the sibling **gitops** repo, and each
cluster's ArgoCD pulls the change. Nothing in this repo ever `kubectl`s a cluster.

## Auth model
CI/CD uses OIDC — there are no stored AWS credentials anywhere in this repo. Never add `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` to GitHub secrets, `.env`, or any config file. The deploy IAM roles are **hardcoded ARNs in each workflow's `env:`** (not secrets): the ops-account ECR push role (`rs-course-ci-ecr-push`) and the per-env frontend-deploy roles, whose OIDC trust is **ref-locked** — stage's role only matches `refs/heads/main`, prod's only matches `refs/tags/v*`.

## Secrets
Runtime config + app secrets live in SSM Parameter Store as SecureStrings under `/rs-course/<env>/app/*` (published by the infra repo's `app-config` unit, synced into the cluster by External Secrets — never read by CI). To read a parameter locally:
```bash
aws ssm get-parameter --name "/rs-course/<env>/app/<param>" --with-decryption
```
The only **GitHub** secrets the pipeline uses: `CI_BOT_APP_ID` + `CI_BOT_PRIVATE_KEY` (the `rs-course-ci-bot` GitHub App — Contents R/W on the gitops repo **only**, used to commit tag bumps), and `SLACK_WEBHOOK_NONPROD` / `SLACK_WEBHOOK_PROD` (failure alerts). Never hardcode a value that belongs in SSM; never commit `.env` files with real credentials.

## Production safety
- Never run `alembic upgrade head` directly against the production database — the gitops **api chart's migrate Job** (a pre-install/pre-upgrade Helm hook) handles schema: it bootstraps a fresh DB with `create_all` + `alembic stamp head`, and upgrades an existing one with `alembic upgrade head`. (This honors the invariant that the alembic chain can't run on an empty DB — see `.claude/rules/migrations.md`.)
- Production is deployed **only** by publishing a GitHub Release (`release.yml`, tag `vX.Y.Z`). This promotes the **exact** stage-tested images — they are re-tagged with the version, never rebuilt. See `docs/release-process.md`.
- **Rollback = revert in gitops**, not in this repo: revert the offending tag-bump commit in the gitops repo (or point the env at a prior tag) and ArgoCD reconciles back. That restores **app code only** — it does not undo a migration, so migrations must stay backward-compatible (expand now, contract a release later). `redeploy-frontend.yml` is the frontend-only equivalent (S3 + CloudFront respin).

## CI/CD workflows (`.github/workflows/`)

Trunk-based **continuous delivery**: merge to `main` → CI green → build (per-image content tag) → gitops **stage** bump → ArgoCD syncs → smoke. Prod is a separate manual act (publish a Release). `main` is the only long-lived branch (no `develop`).

**Per-image content tags.** stage/prod tag each image (`base`/`api`/`worker`) by a hash of *its own* build inputs, not the commit SHA — computed by the `compute-tags` action. An unchanged service keeps its tag, so `build-images` skips the rebuild (tag already in ECR) and `bump-gitops` writes a no-op, and ArgoCD never rolls a service whose bytes didn't change. The path sets in `compute-tags` may be over-inclusive (a needless rebuild is harmless) but never under-inclusive (a stale image is not); the api/worker sets both include `docker/base.Dockerfile` so a base change cascades into their tags. `/health` reports the **api** tag (`APP_VERSION`), so stage smoke waits on the api tag. Dev keeps a single `pr-<num>-<sha>` tag across all three images (throwaway namespace — churn is a non-issue). Prod re-tags both images to the single release version `vX.Y.Z`.

- `ci.yml` — lint, test, docker-build (change-aware via the `detect-changes` job: docs-only PRs skip backend). A green run on a `push` to `main` is what triggers delivery. Never cancel in-flight runs on `main` (only PRs) — cancelling would silently skip the deploy.
- `cd.yml` — **stage** delivery. Triggered by `ci.yml` **completion** (`workflow_run`) for a `push` to `main` with `conclusion == success` (so a commit ships only after its own tests pass). `compute-tags` → builds only the changed images among base + api + worker (per-image content tag → ops ECR) → `bump-gitops` stage → `deploy-frontend` → `smoke-check` (on the api tag). Serialized (`concurrency: cd-stage`, never cancelled). **Prod is not deployed here.**
- `deploy-dev.yml` — label-gated dev deploys. Put the `deploy` label on a PR and every push builds `pr-<num>-<sha>` images and bumps the gitops **dev** env; remove the label to stop. Dev is one shared namespace, so newer runs supersede older (`concurrency: deploy-dev`, cancel-in-progress).
- `release.yml` — **prod** promotion, on `release: published`. Validates the tag is `vX.Y.Z`, re-runs `compute-tags` on the release commit to locate the exact stage-built images, **re-tags** each with the version (no rebuild — byte-identical to what was smoked), `bump-gitops` prod → `deploy-frontend` prod → `smoke-check`. The prod frontend role's OIDC trust matches only `refs/tags/v*`, so it cannot run from a branch.
- `redeploy-frontend.yml` — manual (`workflow_dispatch`), frontend-only S3 + CloudFront respin for a recreated bucket. Ref-locked: stage from `main`, prod from a `vX.Y.Z` tag.
- `security-audit.yml` — weekly pip-audit for CVEs.
- `stale.yml` — weekly stale-issue sweep.

Composite actions (`.github/actions/`): `compute-tags` (per-image content tags for base/api/worker), `build-images` (base + api + worker → ops ECR, skipping any image whose content tag is already in ECR), `bump-gitops` (mints a short-lived GitHub App installation token, commits the per-service tag bump to the gitops repo — **the only path to a cluster**; retries on concurrent-push races), `deploy-frontend` (build + S3 sync + CloudFront invalidation), `smoke-check` (polls the env's public `/health` until the reported version equals the shipped tag — i.e. until ArgoCD has converged — then asserts a real API endpoint answers), `notify-slack` (posts to the env's Slack webhook on failure).

When editing workflows:
- Preserve the `detect-changes` job in `ci.yml` — it prevents unnecessary rebuilds.
- OIDC permissions block must stay on any job that calls AWS or mints the app token (`id-token: write`, `contents: read`).
- `cd.yml` must trigger off `ci.yml` **`workflow_run` success**, not a raw `push` — that's what guarantees a commit ships only after its own tests pass.
- Keep `bump-gitops` as the sole route to a cluster — never add `kubectl`/`helm`/`argocd` cluster credentials to a workflow. CI writes desired state to git; ArgoCD reconciles.
- Don't hardcode the prod frontend role onto a branch-triggered job — its OIDC trust is ref-locked to `refs/tags/v*` and will (correctly) refuse.

## Sibling repos
Two sibling repos hold everything outside the app itself — **do not modify either from this repo** (though CI does commit image-tag bumps to gitops via the bot):
- `rs-recruiting-course-infra` — Terragrunt IaC: AWS org (management/ops/non-prod/prod accounts), EKS, RDS (pgvector), SQS, S3, ECR, cluster add-ons, and the `app-config` unit that publishes SSM config.
- `rs-recruiting-course-gitops` — Helm charts + per-env desired state; ArgoCD's source of truth. Images build once into the **ops account** ECR (`883627150418…`, repos `rs-recruiting-course/{api,worker}`) and are pulled cross-account by every env.

## Observability
- Sentry: backend DSN in SSM, frontend DSN in build args
- In-cluster kube-prometheus-stack (Grafana + Loki datasource); CloudWatch alarms → SNS `ops-alerts`
- Inspector2 scans ECR images on push
