# Release Process

Trunk-based **GitOps continuous delivery**. `main` is the only long-lived branch.
Every commit that lands on `main` and passes CI is built once and shipped to
**stage** automatically. **Prod** is a separate, gated act: a human cuts a
**per-service** release, and each service (api / worker / frontend) versions and
ships **independently** — releasing `api-v1.4.0` never touches worker or frontend.

CI never touches a cluster. It builds images and commits image-tag bumps to the
gitops repo; each cluster's ArgoCD reconciles the change.

```
merge to main   → CI green → build (content tag) → bump gitops STAGE → ArgoCD → smoke
Cut release api → compute semver → push api-vX.Y.Z tag
     └─ tag push → re-tag stage image → bump gitops PROD (api only) → ArgoCD → smoke
```

Stage uses **content tags** (a hash of each image's own build inputs); prod uses
**per-service semver** tags (`<service>-vX.Y.Z`). Merging to `main` never deploys prod.

## The flow

1. **PR into `main`.** Feature branches go through the ruleset: CI green,
   code-owner review, squash merge with a Conventional Commit title.
   *(Optional: label the PR `deploy` to ship it to the shared **dev** namespace
   while it's open — `deploy-dev.yml` builds `pr-<num>-<sha>` images and bumps the
   gitops dev env. Remove the label to stop.)*

2. **Stage is automatic.** When CI passes on the merge commit, `cd.yml` (triggered
   off CI *completion* for a `push` to `main`, so a commit only ships after its own
   tests are green) builds the base + api + worker images, tags them by commit SHA,
   pushes them to the **ops-account ECR**, commits the tag into the gitops repo's
   `stage` env (`bump-gitops`), deploys the frontend (S3 + CloudFront), and
   smoke-checks the public domain once ArgoCD has converged.

3. **Promote to prod (per service).** Run the **Cut release** workflow
   (`release.yml`, `workflow_dispatch`) and pick a service. It computes the next
   semver from the conventional commits that touched that service since its last
   tag (`scripts/ci/next-version.sh`) and pushes `<service>-vX.Y.Z` — no version is
   typed by hand. The tag push triggers `deploy-prod.yml`, which for **api/worker**
   re-tags that commit's existing stage image with the version (byte-identical to
   what was smoked — no rebuild) and bumps **only that service's** key in the gitops
   `prod` env; for **frontend** it rebuilds + syncs S3/CloudFront. `deploy-prod.yml`
   runs *from the tag ref*, so the prod frontend role's `refs/tags/frontend-v*`
   ref-lock still applies; it cannot run from a branch. Both smoke-check on
   `/health` — api against `version`, worker against `worker_version` (the worker
   upserts its tag into a heartbeat row on startup, since it has no HTTP surface).

   > The tag is pushed with the `rs-course-ci-bot` App token, not the default
   > `GITHUB_TOKEN` — a `GITHUB_TOKEN` push would not trigger `deploy-prod.yml`.

## Backing out a bad change

- **Before it reaches prod:** `git revert` the bad commit on `main`; the next
  delivery ships a clean build to stage. Simply don't cut a release.
- **Already in prod:** revert the offending tag-bump commit in the **gitops** repo
  (or point that service's prod env at a prior tag) — ArgoCD reconciles back in
  minutes, no rebuild. Then `git revert` on `main` in this repo so source matches
  the deployed state and the next delivery doesn't re-ship the bad commit.
- **Frontend-only respin** (e.g. a recreated S3 bucket): run `redeploy-frontend.yml`
  (manual) — stage from `main`, prod from a `frontend-vX.Y.Z` tag.

> ⚠️ A rollback restores previous **app code only** — it does **not** undo a
> database migration. Migrations must stay backward-compatible with the running
> version (**expand now, contract a release later**), or a rollback will run old
> code against a new schema. See `.claude/rules/migrations.md`.

## Workflow reference

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | PR / push / merge_group | Lint, test, docker-build (change-aware) |
| `cd.yml` | CI completion on `main` (push) | Build (content tag) → bump gitops **stage** → deploy frontend → smoke |
| `release.yml` (**Cut release**) | Manual (pick a service) | Compute semver → push `<service>-vX.Y.Z` tag (no cloud creds) |
| `deploy-prod.yml` | Push of a `<service>-v*` tag | Re-tag stage image (api/worker) → bump gitops **prod** (that key) → smoke; or frontend respin |
| `deploy-dev.yml` | PR labeled `deploy` (+ pushes) | Build `pr-<num>-<sha>` → bump gitops **dev** |
| `redeploy-frontend.yml` | Manual | Frontend-only S3 + CloudFront respin (ref-locked per env) |
| `security-audit.yml` | Weekly | pip-audit for CVEs |

## Composite actions

`build-images` (base + api + worker → ops ECR) · `bump-gitops` (mint a GitHub App
token, commit the tag bump to the gitops repo — the only path to a cluster) ·
`deploy-frontend` (`npm run build` + S3 sync + CloudFront invalidation) ·
`smoke-check` (poll the public `/health` until the shipped version is live, then
assert an API endpoint answers) · `notify-slack` (failure alerts).

## Environments & accounts

Dev + stage run in the **non-prod** account/cluster; prod is its own
account/cluster. Images build once into the **ops-account** ECR and are pulled
cross-account. CI authenticates via OIDC (ECR push role + per-env frontend deploy
roles, ref-locked) and holds no cluster credentials — the only write to a cluster's
desired state is the gitops tag-bump commit. See
[`INFRASTRUCTURE.md`](./INFRASTRUCTURE.md).

## Version tags

Each service has its **own** version line under a prefixed tag — `api-vX.Y.Z`,
`worker-vX.Y.Z`, `frontend-vX.Y.Z` — so they release independently rather than in
lockstep. `scripts/ci/next-version.sh <service>` computes the next version from the
Conventional Commits that touched that service's path set (the same sets
`compute-tags` uses) since its last tag; **Cut release** runs it for you, so no
version is calculated by hand:

- any `!:` breaking-change marker or `BREAKING CHANGE:` footer → major
- `feat:` → minor
- everything else → patch

Tags are plain git tags, not GitHub Releases — the releases page stays clean, and
each tag is the immutable anchor a prod deploy promotes.
