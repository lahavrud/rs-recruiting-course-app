# Release Process

Trunk-based **GitOps continuous delivery**. `main` is the only long-lived branch.
Every commit that lands on `main` and passes CI is built once and shipped to
**stage** automatically. **Prod** is promoted by a human publishing a GitHub
Release — which re-tags the exact stage-tested images, no rebuild.

CI never touches a cluster. It builds images and commits image-tag bumps to the
gitops repo; each cluster's ArgoCD reconciles the change.

```
merge to main → CI green → build image (by SHA) → bump gitops STAGE → ArgoCD syncs → smoke
publish Release vX.Y.Z    → re-tag stage images   → bump gitops PROD  → ArgoCD syncs → smoke
```

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

3. **Promote to prod.** Publish a GitHub Release with a `vX.Y.Z` tag on a `main`
   commit that already shipped to stage. `release.yml` validates the tag, re-tags
   that commit's existing stage images with the version (byte-identical to what was
   smoked — no rebuild), bumps the gitops `prod` env, deploys the frontend, and
   smoke-checks. The prod frontend deploy role's OIDC trust matches only
   `refs/tags/v*`, so this cannot run from a branch.

## Backing out a bad change

- **Before it reaches prod:** `git revert` the bad commit on `main`; the next
  delivery ships a clean build to stage. Simply don't cut a Release.
- **Already in prod:** revert the offending tag-bump commit in the **gitops** repo
  (or point the prod env at a prior tag) — ArgoCD reconciles back in minutes, no
  rebuild. Then `git revert` on `main` in this repo so source matches the deployed
  state and the next delivery doesn't re-ship the bad commit.
- **Frontend-only respin** (e.g. a recreated S3 bucket): run `redeploy-frontend.yml`
  (manual) — stage from `main`, prod from a `vX.Y.Z` tag.

> ⚠️ A rollback restores previous **app code only** — it does **not** undo a
> database migration. Migrations must stay backward-compatible with the running
> version (**expand now, contract a release later**), or a rollback will run old
> code against a new schema. See `.claude/rules/migrations.md`.

## Workflow reference

| Workflow | Trigger | Does |
|---|---|---|
| `ci.yml` | PR / push / merge_group | Lint, test, docker-build (change-aware) |
| `cd.yml` | CI completion on `main` (push) | Build by SHA → bump gitops **stage** → deploy frontend → smoke |
| `release.yml` | GitHub Release published (`vX.Y.Z`) | Re-tag stage images → bump gitops **prod** → deploy frontend → smoke |
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

A `vX.Y.Z` tag covers the backend image (API + worker run from the same image with
different commands) and the frontend bundle — they deploy in lockstep and share the
same release value for Sentry correlation. `scripts/compute_next_release_tag.sh` is
a manual helper that suggests the next version from the Conventional Commits since
the last tag:

- any `!:` breaking-change marker or `BREAKING CHANGE:` footer → major
- `feat:` → minor
- everything else → patch
