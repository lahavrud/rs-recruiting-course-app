#!/usr/bin/env bash
# Compute the next semantic version for ONE service from the conventional
# commits that have touched that service since its last <service>-v* tag.
# Prints the bare version (X.Y.Z) to stdout; diagnostics go to stderr. A pure
# function — no tagging, no workflow coupling (cut-release.sh is the caller).
#
# Bump rule (highest wins across the range):
#   major — a commit header with `!` (feat!: / fix(x)!:) or a `BREAKING CHANGE` footer
#   minor — any `feat` commit
#   patch — any other conventional commit (fix/chore/refactor/…)
#
# Path scoping mirrors the compute-tags action's per-image sets, so a service's
# version only advances when something that actually feeds it changed. The sets
# may be over-inclusive (a needless version bump is harmless) but never
# under-inclusive. `libs/shared` and `docker/base.Dockerfile` sit in both api
# and worker, so a shared/base change can bump both — intentional.
#
# Exit codes: 0 computed a version · 2 bad usage · 3 nothing to release
set -euo pipefail

service="${1:?usage: next-version.sh <api|worker|frontend>}"

case "$service" in
  api)
    paths=(docker/base.Dockerfile pyproject.toml uv.lock libs/shared services/api
           services/worker/pyproject.toml alembic alembic.ini scripts
           frontend/src/content/articles docker-entrypoint.sh) ;;
  worker)
    paths=(docker/base.Dockerfile pyproject.toml uv.lock libs/shared services/worker
           services/api/pyproject.toml docker-entrypoint.sh) ;;
  frontend)
    paths=(frontend) ;;
  *)
    echo "next-version: unknown service '$service' (want api|worker|frontend)" >&2
    exit 2 ;;
esac

# Newest existing release tag for this service. version:refname sorts on the
# embedded version numbers; the prefix is constant so ordering is by semver.
# Read via process substitution (not `| tail`) so pipefail can't trip on a
# SIGPIPE when git's output is truncated.
mapfile -t _tags < <(git tag --list "${service}-v*" --sort=version:refname)
if ((${#_tags[@]})); then last_tag="${_tags[-1]}"; else last_tag=""; fi

if [[ -z "$last_tag" ]]; then
  range=()            # whole history — first release of this service
  base="0.0.0"
else
  range=("${last_tag}..HEAD")
  base="${last_tag#"${service}-v"}"
fi

# Commits since the last tag that touched this service's paths.
mapfile -t commits < <(git log "${range[@]}" --format='%H' -- "${paths[@]}")
if [[ ${#commits[@]} -eq 0 ]]; then
  echo "next-version: no commits touching ${service} since ${last_tag:-repo start} — nothing to release" >&2
  exit 3
fi

bump=patch
for sha in "${commits[@]}"; do
  body=$(git log -1 --format='%B' "$sha")
  header=${body%%$'\n'*} # first line, without a SIGPIPE-prone `| head`
  if [[ "$body" == *"BREAKING CHANGE"* || "$body" == *"BREAKING-CHANGE"* ]] \
     || [[ "$header" =~ ^[a-z]+(\([^\)]*\))?!: ]]; then
    bump=major
    break
  fi
  if [[ "$header" =~ ^feat(\([^\)]*\))?: ]]; then
    bump=minor
  fi
done

IFS=. read -r major minor patch <<<"$base"
case "$bump" in
  major) major=$((major + 1)); minor=0; patch=0 ;;
  minor) minor=$((minor + 1)); patch=0 ;;
  patch) patch=$((patch + 1)) ;;
esac
version="${major}.${minor}.${patch}"

echo "next-version: ${service} ${last_tag:-<none>} + ${bump} -> v${version}" >&2
echo "${version}"
