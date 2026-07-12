#!/usr/bin/env bash
# Parse a `<service>-vX.Y.Z` release tag into its service and version, printing
# them as `key=value` lines (the detect-changes.sh idiom — the workflow
# redirects stdout to $GITHUB_OUTPUT). Fails loudly on a malformed tag.
#
# Usage: parse-release-tag.sh <tag>   e.g. parse-release-tag.sh api-v1.4.0
set -euo pipefail

tag="${1:?usage: parse-release-tag.sh <service>-vX.Y.Z}"
if [[ ! "$tag" =~ ^(api|worker|frontend)-v([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  echo "parse-release-tag: '$tag' is not <service>-vX.Y.Z" >&2
  exit 1
fi

echo "service=${BASH_REMATCH[1]}"
echo "version=v${BASH_REMATCH[2]}"
