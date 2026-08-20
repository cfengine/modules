#!/usr/bin/env bash
set -ex
thisdir="$(dirname "$0")"
bash "$thisdir"/deploy.sh
if ls "$thisdir"/0*.sh >/dev/null; then
  bash "$thisdir"/0*.sh
fi
