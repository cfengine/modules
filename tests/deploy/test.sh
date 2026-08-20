#!/usr/bin/env bash
set -ex
thisdir="$(dirname "$0")"
bash "$thisdir"/deploy.sh
if ls "$thisdir"/0*.sh >/dev/null; then
  for test in "$thisdir"/0*.sh; do
    bash -ex "$test"
  done
fi
