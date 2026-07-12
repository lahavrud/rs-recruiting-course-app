# AWS & Infrastructure Rules

This repo ships to Kubernetes via **strict GitOps**: CI has no cluster credentials —
it builds images and commits image-tag bumps to the sibling **gitops** repo, and each
cluster's ArgoCD pulls the change. Nothing in this repo ever `kubectl`s a cluster.

## Auth model
CI/CD uses OIDC — there are no stored AWS credentials anywhere in this repo. Never add `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` to GitHub secrets, `.env`, or any config file. The deploy IAM roles are **hardcoded ARNs in each workflow's `env:`** (not secrets): the ops-account ECR push role (`rs-course-ci-ecr-push`, trusts `refs/heads/main`, `refs/tags/*-v*` for per-service prod releases, and PR runs) and the per-env frontend-deploy roles, whose OIDC trust is **ref-locked** — stage's role only matches `refs/heads/main`, prod's only matches `refs/tags/frontend-v*`. (Ref patterns are defined in the infra repo — the ops `github-oidc` unit and the frontend module's `github_refs`.)

## Secrets
Runtime config + app secrets live in SSM Parameter Store as SecureStrings under `/rs-course/<env>/app/*` (published by the infra repo's `app-config` unit, synced into the cluster by External Secrets — never read by CI). To read a parameter locally:
```bash
aws ssm get-parameter --name "/rs-course/<env>/app/<param>" --with-decryption
```
The only **GitHub** secrets the pipeline uses: `CI_BOT_APP_ID` + `CI_BOT_PRIVATE_KEY` (the `rs-course-ci-bot` GitHub App — Contents R/W on the gitops repo **only**, used to commit tag bumps), and `SLACK_WEBHOOK_NONPROD` / `SLACK_WEBHOOK_PROD` (failure alerts). Never hardcode a value that belongs in SSM; never commit `.env` files with real credentials.

## Production safety
- Never run `alembic upgrade head` directly against the production database — the gitops **api chart's migrate Job** (a pre-install/pre-upgrade Helm hook) handles schema: it bootstraps a fresh DB with `create_all` + `alembic stamp head`, and upgrades an existing one with `alembic upgrade head`. (This honors the invariant that the alembic chain can't run on an empty DB — see `.claude/rules/migrations.md`.)
- Production is deployed **only** by cutting a per-service release: run `release.yml` (Cut release) for a service → it computes the next semver from conventional commits and pushes `<service>-vX.Y.Z` → the tag triggers `deploy-prod.yml`, which promotes the **exact** stage-tested image (re-tagged with the version, never rebuilt). Each service versions independently. See `docs/release-process.md`.
- **Rollback = revert in gitops**, not in this repo: revert the offending tag-bump commit in the gitops repo (or point the env at a prior tag) and ArgoCD reconciles back. That restores **app code only** — it does not undo a migration, so migrations must stay backward-compatible (expand now, contract a release later). `redeploy-frontend.yml` is the frontend-only equivalent (S3 + CloudFront respin).

## CI/CD workflows (`.github/workflows/`)

Trunk-based **continuous delivery**: merge to `main` → CI green → build (per-image content tag) → gitops **stage** bump → ArgoCD syncs → smoke. Prod is a separate, gated act — a human cuts a per-service release. `main` is the only long-lived branch (no `develop`).

**Two tracks, two tag schemes.** *Stage* uses **content tags** (auto, every merge); *prod* uses **per-service semver** (`api-vX.Y.Z` / `worker-vX.Y.Z` / `frontend-vX.Y.Z`), and each service versions and ships independently. Merging to `main` never deploys prod.

**Per-image content tags (stage/dev).** Each image (`base`/`api`/`worker`) is tagged by a hash of *its own* build inputs, not the commit SHA — computed by the `compute-tags` action. An unchanged service keeps its tag, so `build-images` skips the rebuild (tag already in ECR) and `bump-gitops` writes a no-op, and ArgoCD never rolls a service whose bytes didn't change. The path sets in `compute-tags` may be over-inclusive (a needless rebuild is harmless) but never under-inclusive (a stale image is not); the api/worker sets both include `docker/base.Dockerfile` so a base change cascades into their tags. `/health` reports the **api** tag (`APP_VERSION`), so smoke waits on the api tag. Dev keeps a single `pr-<num>-<sha>` tag across all three images (throwaway namespace — churn is a non-issue).

**Per-service semver (prod).** `scripts/ci/next-version.sh <service>` derives the next version from the conventional commits that touched that service's `compute-tags` path set since its last `<service>-v*` tag (`feat`→minor, `BREAKING CHANGE`/`!`→major, else patch). A prod release re-tags **only that one service's** proven stage image to the version and bumps **only that key** in gitops.

- `ci.yml` — lint, test, docker-build (change-aware via the `detect-changes` job: docs-only PRs skip backend). A green run on a `push` to `main` is what triggers delivery. Never cancel in-flight runs on `main` (only PRs) — cancelling would silently skip the deploy.
- `cd.yml` — **stage** delivery. Triggered by `ci.yml` **completion** (`workflow_run`) for a `push` to `main` with `conclusion == success` (so a commit ships only after its own tests pass). `compute-tags` → builds only the changed images among base + api + worker (per-image content tag → ops ECR) → `bump-gitops` stage → `deploy-frontend` → `smoke-check` (on the api tag). Serialized (`concurrency: cd-stage`, never cancelled). **Prod is not deployed here.**
- `deploy-dev.yml` — label-gated dev deploys. Put the `deploy` label on a PR and every push builds `pr-<num>-<sha>` images and bumps the gitops **dev** env; remove the label to stop. Dev is one shared namespace, so newer runs supersede older (`concurrency: deploy-dev`, cancel-in-progress).
- `release.yml` (**Cut release**) — the human prod gate. Manual (`workflow_dispatch`, pick a service); `scripts/ci/cut-release.sh` computes the next version and pushes `<service>-vX.Y.Z`. Holds **no** cloud creds — it only tags. The tag MUST be pushed with the `rs-course-ci-bot` App token (needs Contents:write on **this** repo), because a tag pushed by the default `GITHUB_TOKEN` would not trigger `deploy-prod.yml`.
- `deploy-prod.yml` — **prod** promotion, on `push:` of a `*-v*` tag (so it runs **from the tag ref** — that's what keeps the prod frontend role's `refs/tags/frontend-v*` ref-lock meaningful). `parse-release-tag.sh` → for api/worker: `compute-tags` locates the exact stage image, `retag-images.sh` re-tags **that one** to the version, `bump-gitops` bumps **only that key**; api then smokes on `/health` (worker ships blind — no public surface yet). For frontend: `deploy-frontend` + `verify-spa.sh`.
- `redeploy-frontend.yml` — manual (`workflow_dispatch`), frontend-only S3 + CloudFront respin for a recreated bucket. Ref-locked: stage from `main`, prod from a `frontend-vX.Y.Z` tag.
- `security-audit.yml` — weekly pip-audit for CVEs.
- `stale.yml` — weekly stale-issue sweep.

Composite actions (`.github/actions/`): `compute-tags` (per-image content tags for base/api/worker), `build-images` (base + api + worker → ops ECR, skipping any image whose content tag is already in ECR), `bump-gitops` (mints a short-lived GitHub App installation token, commits a tag bump to the gitops repo — **the only path to a cluster**; `api-tag`/`worker-tag` are both optional so a per-service prod release bumps just one key, while stage/dev pass both; retries on concurrent-push races), `deploy-frontend` (build + S3 sync + CloudFront invalidation), `smoke-check` (polls the env's public `/health` until the reported version equals the shipped tag — i.e. until ArgoCD has converged — then asserts a real API endpoint answers), `notify-slack` (posts to the env's Slack webhook on failure).

When editing workflows:
- Preserve the `detect-changes` job in `ci.yml` — it prevents unnecessary rebuilds.
- OIDC permissions block must stay on any job that calls AWS or mints the app token (`id-token: write`, `contents: read`).
- `cd.yml` must trigger off `ci.yml` **`workflow_run` success**, not a raw `push` — that's what guarantees a commit ships only after its own tests pass.
- Keep `bump-gitops` as the sole route to a cluster — never add `kubectl`/`helm`/`argocd` cluster credentials to a workflow. CI writes desired state to git; ArgoCD reconciles.
- Don't hardcode the prod frontend role onto a branch-triggered job — its OIDC trust is ref-locked to `refs/tags/frontend-v*` and will (correctly) refuse.
- `deploy-prod.yml` must stay triggered by the **tag push** (not `workflow_dispatch`) so it runs from the tag ref — that's what satisfies the prod frontend role's ref-lock. And `release.yml` must push the tag with the **App token**, never `GITHUB_TOKEN` (which wouldn't trigger `deploy-prod.yml`).

## Sibling repos
Two sibling repos hold everything outside the app itself — **do not modify either from this repo** (though CI does commit image-tag bumps to gitops via the bot):
- `rs-recruiting-course-infra` — Terragrunt IaC: AWS org (management/ops/non-prod/prod accounts), EKS, RDS (pgvector), SQS, S3, ECR, cluster add-ons, and the `app-config` unit that publishes SSM config.
- `rs-recruiting-course-gitops` — Helm charts + per-env desired state; ArgoCD's source of truth. Images build once into the **ops account** ECR (`883627150418…`, repos `rs-recruiting-course/{api,worker}`) and are pulled cross-account by every env.

## Observability
- Sentry: backend DSN in SSM, frontend DSN in build args
- In-cluster kube-prometheus-stack (Grafana + Loki datasource); CloudWatch alarms → SNS `ops-alerts`
- Inspector2 scans ECR images on push
