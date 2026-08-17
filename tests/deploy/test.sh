#!/usr/bin/env bash
set -ex

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
sudo cf-agent -IB 127.0.0.1

sudo cf-agent -KI -Ddata:install_ansible -Ddata:ansible_minimal_install --bundle install_ansible > log
if grep -qiP '(err|fail|notkept)' log; then
  cat log
  exit 1
fi

# test for minimal versus full install
ansible --version # will fail test if not available or not executable
