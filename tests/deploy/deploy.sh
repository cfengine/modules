#!/usr/bin/env bash
set -ex

echo "WARNING/TODO: This test, $0, requires all changes to be pushed up to a branch in order to test the latest. This could be improved if cfbs add could work with the modules repo and a cfbs.json file. See ENT-14421"
if [ -n "$GITHUB_HEAD_REF" ]; then
  # github case
  BRANCH="$GITHUB_HEAD_REF"
else
  # local case
  BRANCH=$(git rev-parse --abbrev-ref HEAD)
fi

# workaround, if git@ url then we get Error: Cannot specify more than one version of the same module
# so transform the remote url
REPO=$(git remote get-url origin | \
  sed -e 's,git@,https://,' \
      -e 's,com:,com/,' \
)

if [ -n "$GITHUB_HEAD_REF" ]; then
  REPO="$(echo "$REPO" | sed -e "s,cfengine,$GITHUB_TRIGGERING_ACTOR,")"
fi

thisdir="$(dirname "$0")"
cd "$thisdir"
[ -d .git ] && rm -rf .git
[ -f cfbs.json ] && rm cfbs.json
cfbs --version
cfbs init --non-interactive
cfbs --non-interactive add "$REPO@$BRANCH"
cfbs build
sudo cfbs install
sudo cf-agent -IB 127.0.0.1 > log

if grep 'error:' log; then
  grep 'error:' log
  exit 1
fi

