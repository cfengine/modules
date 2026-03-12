# `sshd` promise type

Configures sshd and restarts the service when configuration changes.

## Promiser
An arbitrary human-readable label that appears in log messages and reports.
Since there is only one global sshd configuration, the promiser is not used to identify a resource.
Example: `"global sshd config"`.

## Attributes
- Named using sshd's native directive names (e.g. `PermitRootLogin`, not `permit_root_login`)
- Values can be strings or slists
- Validated against `sshd -G` during promise validation

## What the module manages internally
1. **Include directive** — ensures the base `sshd_config` includes the drop-in directory (`sshd_config.d/`) as its first non-comment directive
2. **Drop-in directory** — creates the drop-in directory if it doesn't exist
3. **Drop-in file** — writes directives to `sshd_config.d/00-cfengine.conf`
4. **Service restart** — restarts sshd if configuration was changed and the service is already running
5. **Verification** — verifies the desired attributes appear in the effective sshd config (`sshd -T`)

## What the module does NOT do
- Install sshd — that is a `packages:` promise
- Ensure sshd is running — that is a `services:` promise
- Manage match blocks — those are a policy-level concern

## Policy
```cf3
bundle agent sshd_config
{
  packages:
      "openssh-server"
          policy => "present";

  services:
      "sshd"
          service_policy => "start";

  vars:
      "allowed_users" slist => { "alice", "bob" };

  sshd:
      "global"
          PermitRootLogin        => "no",
          PasswordAuthentication => "no",
          Port                   => "22",
          AllowUsers             => @(allowed_users);
}
```

## Authors

This software was created by the team at [Northern.tech](https://northern.tech), with many contributions from the community.
Thanks everyone!

## Contribute

Feel free to open pull requests to expand this documentation, add features, or fix problems.
You can also pick up an existing task or file an issue in [our bug tracker](https://northerntech.atlassian.net/).

## License

This software is licensed under the MIT License. See LICENSE in the root of the repository for the full license text.
