#!/usr/bin/env bash
set -ex
thisdir="$(dirname "$0")"
thispath="$(realpath "$thisdir")"

# todo, confirm minimal and full installs somehow by checking commands or modules or ???
sudo cf-agent  -Kvf "$thispath"/../software/install-ansible.cf -Ddata:install_ansible -Ddata:ansible_minimal_install  --bundle install_ansible | tee "$0.log"
grep -E '(err|fail)' "$0.log"

command -v pipx
command -v ansible
