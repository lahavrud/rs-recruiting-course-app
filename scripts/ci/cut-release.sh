#!/usr/bin/env bash
# Cut a release for ONE service: compute the next version (next-version.sh),
# then create and push the `<service>-vX.Y.Z` tag. The push must run on a
# checkout whose origin carries the CI-bot App token (release.yml sets it) so
# the tag push triggers deploy-prod.yml — a GITHUB_TOKEN push would not.
#
# A "nothing to release" result (next-version.sh exit 3) is a clean no-op:
# writes a note to the step summary and exits 0.
#
# Usage: cut-release.sh <api|worker|frontend>
set -euo pipefail

service="${1:?usage: cut-release.sh <api|worker|frontend>}"
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
summary="${GITHUB_STEP_SUMMARY:-/dev/null}"

if version=$("$here/next-version.sh" "$service"); then
  :
else
  rc=$?
  if [ "$rc" -eq 3 ]; then
    {
      echo "### Nothing to release"
      echo "No commits have touched \`${service}\` since its last tag."
    } >> "$summary"
    exit 0
  fi
  exit "$rc"
fi

tag="${service}-v${version}"
if git rev-parse -q --verify "refs/tags/${tag}" >/dev/null; then
  echo "cut-release: tag ${tag} already exists" >&2
  exit 1
fi

git config user.name "rs-course-ci-bot[bot]"
git config user.email "rs-course-ci-bot[bot]@users.noreply.github.com"
git tag -a "$tag" -m "Release ${tag}"
git push origin "refs/tags/${tag}"

{
  echo "### Cut \`${tag}\`"
  echo "deploy-prod.yml will promote it to prod (retag image + gitops bump, or frontend respin)."
} >> "$summary"
