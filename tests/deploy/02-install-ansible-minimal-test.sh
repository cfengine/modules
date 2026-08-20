#!/usr/bin/env bash
set -ex

sudo pipx uninstall --global ansible || true
sudo pipx uninstall --global ansible-core || true

sudo cf-agent -Kd -Ddata:install_ansible -Ddata:ansible_minimal_install --bundle install_ansible > log
if grep 'error:' log; then
  grep 'error:' log
  exit 1
fi

ansible --version
if ! ( sudo pipx list --global --short | grep ansible-core ); then
  echo "expected ansible-core to be installed but did not find that in pipx list output"
fi
