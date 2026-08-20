This module ensures that Ansible is installed on a system.

## Configuration

There are three classes which can be used to specify whether to install ansible and which version: minimal or full.

- `data:install_ansible` - if defined, install ansible (default is full install)
- `data:ansible_minimal_install` - if defined, install minimal version aka ansible-core
- `data:ansible_full_install` - if defined, install full version.

Additionally it is possible to request a specific version other than the latest/default by way of a variable.

- `data:install_ansible.version` - if this variable is defined then a specific version will be installed

Note that the system in question must have a `pipx` package available through the default package manager as well as python installed which should come along as a dependency of `pipx`.
