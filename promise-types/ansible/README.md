The `ansible` promise type allows you to run Ansible playbooks from within CFEngine policy.

For example, you can play the `/northern.tech/playbook.yaml` playbook locally, using `/northern.tech/inventory.yaml`, and limiting the execution to the `helloworld` tag:

```cfengine3
bundle agent main
{
  ansible:
    "my_playbook"
      playbook   => "/northern.tech/playbook.yaml",
      inventory  => "/northern.tech/inventory.yaml",
      tags       => {"helloworld"};
}
```

## Requirements

* Ansible >= 2.8.0

## Attributes

| Name               | Type      | Description                                                  | Mandatory | Default         |
| ------------------ | --------- | ------------------------------------------------------------ | --------- | --------------- |
| `playbook`         | `string`  | Absolute path of the Ansible playbook                        | No        | Promiser        |
| `inventory`        | `string`  | Absolute path of the inventory file                          | No        | -               |
| `limit`            | `slist`   | List of host names to target                                 | No        | `{"localhost"}` |
| `tags`             | `slist`   | List of tags to play                                         | No        | `{}`            |
| `become`           | `boolean` | Set the `become` option                                      | No        | `False`         |
| `become_method`    | `string`  | Set the `become_method` option                               | No        | `"sudo"`        |
| `become_user`      | `string`  | Set the `become_user` option                                 | No        | `root`          |
| `connection`       | `string`  | Set the `connection` option; possible values: `local`, `ssh` | No        | `local`         |
| `forks`            | `int`     | Set the `forks` option                                       | No        | `1`             |
| `private_key_file` | `string`  | Absolute path of the SSH private key to use                  | No        | -               |
| `remote_user`      | `string`  | Set the `remote_user` option                                 | No        | `root`          |

## Examples

This promise can run ansible over ssh targeting multiple hosts, for example:

```cfengine3
bundle agent main
{
  ansible:
    "my_playbook"
      playbook         => "/northern.tech/playbook.yaml",
      inventory        => "/northern.tech/inventory.yaml",
      become           => "true",
      become_method    => "sudo",
      become_user      => "root",
      connection       => "ssh",
      forks            => int(eval("4 * $(sys.cpus)")),
      remote_user      => "ubuntu",
      limit            => {"host1", "host2", "host3", "host4"},
      private_key_file => "/path/to/your/private/key/id_rsa";
}
```

## Authors

This software was created by the team at [Northern.tech](https://northern.tech), with many contributions from the community.
Thanks everyone!

## Contribute

Feel free to open pull requests to expand this documentation, add features or fix problems.
You can also pick up an existing task or file an issue in [our bug tracker](https://tracker.mender.io/issues/).

## License

This software is licensed under the MIT License. See LICENSE in the root of the repository for the full license text.
