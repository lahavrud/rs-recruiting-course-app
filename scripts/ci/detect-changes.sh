#!/usr/bin/env bash
# Decide which areas of the repo a CI run must exercise, so downstream jobs can
# skip when irrelevant (Actions bills per-job rounded up to the minute).
#
# Emits three `key=value` lines on stdout — the workflow redirects them into
# $GITHUB_OUTPUT:
#   backend=<bool>  frontend=<bool>  docker=<bool>
#
# Inputs (env, all provided natively by GitHub Actions except the two SHAs,
# which the calling step passes through from the PR event):
#   GITHUB_EVENT_NAME   the triggering event
#   BASE_SHA / HEAD_SHA the PR's base and head commits (pull_request only)
#
# Any non-PR event (push to main, merge_group) forces every area on, so the
# delivery gate always runs the full suite.
set -euo pipefail

if [[ "${GITHUB_EVENT_NAME}" != "pull_request" ]]; then
  printf 'backend=true\nfrontend=true\ndocker=true\n'
  exit 0
fi

files=$(git diff --name-only "${BASE_SHA}" "${HEAD_SHA}")
changed() { grep -qE "$1" <<<"${files}"; }

backend=false frontend=false docker=false

# A workflow edit invalidates every assumption — run everything.
changed '^\.github/workflows/' && { backend=true frontend=true docker=true; }

changed '^(libs/|services/|tests/|alembic/|scripts/.*\.py|pyproject\.toml|uv\.lock)' && backend=true
changed '^frontend/' && frontend=true

# docker-build smoke-tests the backend image, so guard it with the same backend
# inputs the image is built from.
changed '^(services/[^/]+/Dockerfile|docker/.*|(libs|services)/[^/]+/pyproject\.toml|pyproject\.toml|uv\.lock|docker-compose.*\.yml)' \
  && { docker=true backend=true; }

printf 'backend=%s\nfrontend=%s\ndocker=%s\n' "${backend}" "${frontend}" "${docker}"
