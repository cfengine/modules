# package-method-ansible-galaxy-collection

## Usage
This module enables a `ansible-galaxy-collection` package method used with policy like:

```cf3
packages:
  "ansible.posix"
    package_method => ansible_galaxy_collection,
    package_policy => "add";
```

Note that there is not a command option in ansible-galaxy to uninstall collections so that will result in no changes being made and a warning message. Ansible documentation suggests [removing collections with rm](https://docs.ansible.com/projects/ansible/latest/collections_guide/collections_installing.html#removing-a-collection)

## Installation

This module does not ensure that needed ansible packages are installed to provide the `ansible-galaxy` command.
Typically this is a package named `ansible` on Debian-based distributions or `ansible-core` on RedHat-based distributions.
