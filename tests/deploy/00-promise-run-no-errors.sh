#!/usr/bin/env bash
# assumes deploy.sh has already run adjacent to this file

set -ex
sudo cf-agent -KI > log
if grep 'error:' log; then
  grep 'error:' log
  exit 1
fi
