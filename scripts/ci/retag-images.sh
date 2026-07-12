#!/usr/bin/env bash
# Promote ONE stage-built image to a release version by re-tagging it in ECR —
# no rebuild, so what ships is byte-identical to what stage smoked.
#
# Re-tagging is server-side: `batch-get-image` fetches an existing image's
# manifest by its stage content tag, and `put-image` writes that same manifest
# back under the version tag. Nothing is pulled or pushed.
#
# Inputs (env; the caller must already hold an ECR-push AWS session):
#   SERVICE      which image to promote: api | worker
#   VERSION      the release tag, e.g. v1.4.0
#   API_SRC      the api image's stage content tag    (used when SERVICE=api)
#   WORKER_SRC   the worker image's stage content tag (used when SERVICE=worker)
set -euo pipefail

retag() {
  local repo=$1 src=$2
  local manifest
  manifest=$(aws ecr batch-get-image \
    --repository-name "$repo" \
    --image-ids imageTag="$src" \
    --query 'images[0].imageManifest' --output text)
  if [[ -z "$manifest" || "$manifest" == "None" ]]; then
    echo "no ${repo}:${src} image — tag a commit that shipped to stage" >&2
    return 1
  fi
  # put-image is idempotent on a re-run: the version tag may already point at
  # this manifest, which ECR rejects with ImageAlreadyExistsException — fine.
  local out
  out=$(aws ecr put-image \
    --repository-name "$repo" \
    --image-tag "$VERSION" \
    --image-manifest "$manifest" 2>&1) \
    || grep -q ImageAlreadyExistsException <<<"$out" \
    || { echo "$out" >&2; return 1; }
  echo "${repo}:${VERSION} ready"
}

case "${SERVICE:?SERVICE must be api or worker}" in
  api)    retag rs-recruiting-course/api    "${API_SRC:?API_SRC required}" ;;
  worker) retag rs-recruiting-course/worker "${WORKER_SRC:?WORKER_SRC required}" ;;
  *) echo "retag-images: unknown SERVICE '$SERVICE' (want api|worker)" >&2; exit 2 ;;
esac
