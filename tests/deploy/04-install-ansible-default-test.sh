#!/usr/bin/env bash
# assumes deploy.sh has already run adjacent to this file

set -ex

sudo pipx uninstall --global ansible || true
sudo pipx uninstall --global ansible-core || true

sudo cf-agent -Kd -Ddata:install_ansible --bundle install_ansible > log
if grep 'error:' log; then
  grep 'error:' log
  exit 1
fi

ansible --version
echo "expect that ansible(full) is installed and not ansible-core"
if ( sudo pipx list --global --short | grep ansible-core ); then
  echo "expected ansible(full) to be installed, but found ansible-core"
  exit 1
fi
