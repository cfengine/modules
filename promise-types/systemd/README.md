The `systemd` promise type lets you create and manage services using systemd.

## Requirements

* A system managed by systemd.

## Attributes

| Name | Type | Description| Mandatory | Default |
| --- | --- | --- | --- | --- |
| `daemon_reexec` | `boolean` | Run daemon-reexec before performing actions to the service | No | `false` |
| `daemon_reload` | `boolean` | Run daemon-reload before performing actions to the service | No | `false` |
| `enabled` | `boolean` | Start the service on boot | No | `true` |
| `masked` | `boolean` | Mask the service, making it impossible to start | No | `false` |
| `name` | `string` | The name of the service | Yes | Promiser |
| `replace` | `boolean` | Replace service unit file if it already exists | No | `True` |
| `state` | `string` | State of the service: `started`, `stopped` and `absent` are idempotent, `restart` and `reload` are not. | Yes | - |
| `unit_description` | `string` | Free-form string describing the unit | No | - |
| `unit_requires` | `slist` | Units which must be started along with the service | No | - |
| `unit_wants` | `slist` | Units which should be started along with the service | No | - |
| `unit_after` | `slist` | Units which must be started after the service | No | - |
| `unit_before` | `slist` | Units which must be started before the service | No | - |
| `unit_extra` | `slist` | Additional lines to append to the `Unit` section of the service file | No | - |
| `service_type` | `string` | Process start-up type, e.g. `simple`, `forking`, etc. | No | - |
| `service_pid_file` | `string` | Absolute file name pointing to the PID file of this daemon | No | - |
| `service_user` | `string` | User under which the service should be executed | No | - |
| `service_group` | `string` | Group under which the service should be executed | No | - |
| `service_nice` | `integer` | Default nice level for the service | No | - |
| `service_oom_score_adjust` | `integer` | Adjustment level for the Out-Of-Memory killer | No | - |
| `service_exec_start` | `slist` | Commands that are executed when this service is started | No | - |
| `service_exec_start_pre` | `slist` | Commands that are executed before `exec_start` commands | No | - |
| `service_exec_start_post` | `slist` | Commands that are executed after `exec_start` commands | No | - |
| `service_exec_stop` | `slist` | Commands to execute to stop the service started via `exec_start` | No | - |
| `service_exec_stop_post` | `slist` | Commands that are executed after the service is stopped | No | - |
| `service_exec_reload` | `slist` | Commands to execute to trigger a configuration reload in the service | No | - |
| `service_restart` | `string` | When the service must be restarted | No | - |
| `service_restart_sec` | `string` | Time to sleep before restarting the service | No | - |
| `service_timeout_sec` | `string` | Maximum waiting time for start/stop commands processing | No | - |
| `service_environment` | `slist` | Environment variables, in the format `key=value` | No | - |
| `service_environment_file` | `string` | Path to a file containing the environment variables | No | - |
| `service_working_directory` | `string` | Working directory | No | - |
| `service_standard_input` | `string` | Path to the standard input file descriptor | No | - |
| `service_standard_output` | `string` | Path to the standard output file descriptor | No | - |
| `service_standard_error` | `string` | Path to the standard error file descriptor | No | - |
| `service_tty_path` | `string` | Path to the tty if required by the `standard_*` options | No | - |
| `service_extra` | `slist` | Additional lines to append to the `Service` section of the service file | No | - |
| `install_wanted_by` | `slist` | Units which are wanted by the service | No | - |
| `install_required_by` | `slist` | Units which are required by the service | No | - |
| `install_extra` | `slist` | Additional lines to append to the `Install` section of the service file | No | - |

## Examples

Make sure service named `myservice` is started:

```cfengine3
bundle agent main
{
  systemd:
    "myservice"
      name => "myservice",
      enabled => "true",
      state => "started";
}
```

Make sure a service `sample` running `sleep 86400` exists:

```cfengine3
bundle agent main
{
  systemd:
    "sample"
      masked => "false",
      enabled => "true",
      state => "started",
      unit_description => "My sample service",
      service_exec_start => {"/usr/bin/sleep 86400"},
      service_type => "simple",
      install_wanted_by => {"multi-user.target"};
}
```

Make sure the service named `sample` does not exist:

```cfengine3
bundle agent main
{
  systemd:
    "sample"
      state => "absent";
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
