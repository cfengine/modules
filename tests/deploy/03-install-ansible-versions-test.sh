#!/usr/bin/env bash
set -ex

sudo pipx uninstall --global ansible || true
sudo pipx uninstall --global ansible-core || true

function cleanup
{
  sudo rm -f /var/cfengine/data/host_specific.json || true # to make sure any version data is removed for other tests other runs
}

trap cleanup EXIT

good_version="2.21.3"

sudo mkdir -p /var/cfengine/data
cat <<EOF | sudo tee /var/cfengine/data/host_specific.json
{
  "vars": {
    "data:install_ansible.version": "$good_version"
  }
}
EOF

sudo cf-agent -Kd -Ddata:install_ansible -Ddata:ansible_minimal_install --bundle install_ansible > log

if grep 'error:' log; then
  grep 'error:' log
  exit 1
fi

ansible --version | grep "${good_version}"

sudo pipx uninstall --global ansible || true
sudo pipx uninstall --global ansible-core || true

bad_version="x.y.z"
cat <<EOF | sudo tee /var/cfengine/data/host_specific.json
{
  "vars": {
    "data:install_ansible.version": "$bad_version"
  }
}
EOF
echo "Evaluating install_ansible bundle expecting an error due to bad version value"
sudo cf-agent -Kd -Ddata:install_ansible -Ddata:ansible_minimal_install --bundle install_ansible > log

if grep 'error:' log; then
  echo "Expected error found due to bad version value. Test passes."
  grep 'error:' log
  exit 0
fi

echo "Expected errors when installing ansible with bad version"
exit 1
