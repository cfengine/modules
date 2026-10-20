This module enables the running of Ansible playbooks based on input from Build in Mission Portal or `cfbs input`.

You point the module at the playbook file itself.
This entails providing an absolute path to the file via command line using cfbs,
or uploading the file in the Mission Portal build app.
The playbook is copied into your project and shipped with the policy set during `cfbs build`.
There is no need to add a playbook directory as a separate module, and no need to write the `$(sys.inputdir)` path by hand.

Only files ending in `.yaml` or `.yml` are accepted.

**Note:** Requires cfbs >= 5.8.0 (bundled with CFEngine 3.29 and newer).

**Note:** The playbooks will be distributed and run locally with root-privilege (uid=0).

**Note:** Ansible must be installed on the hosts.
You can use a module to install Ansible *_(See [install-ansible](https://build.cfengine.com/modules/install-ansible/) build module)_*:
```
cfbs add install-ansible
```

**Usage:**

```
cfbs add ansible-playbook-dispatcher
```

- `path` - The playbook to run. Use an absolute path to `.yaml` or `.yml` file.
- `condition` - Condition for running the playbook.
  Use a class expression (e.g., `linux|bsd`).
  Defaults to `any`.
- `ifelapsed` - Minimum number of minutes between each run.
  Defaults to 5 minutes.

E.g.

```
$ cfbs input ansible-playbook-dispatcher
Collecting input for module 'ansible-playbook-dispatcher'
Which playbook should be run? /tmp/playbook.yaml
Condition for when to run: linux
Number of minutes between playbook assessments: 5
Do you want to specify more playbooks to be run? no
```

Would run `/tmp/playbook.yaml` on every linux device with 5 minute intervals.

**Note:** If you would rather keep your playbooks in a directory of their own and
reference them by path, see the
[run-ansible-playbooks](https://build.cfengine.com/modules/run-ansible-playbooks/) build module.

## Contribute

Feel free to open pull requests to expand this documentation, add features or fix problems.
You can also pick up an existing task or file an issue in [our bug tracker](https://northerntech.atlassian.net/projects/CFE).

## License

This software is licensed under the MIT License. See LICENSE in the root of the repository for the full license text.
