# Iptables Promise Module

## Synopsis
- *Name*: `iptables`
- *Version*: `0.1.1`
- *Description*: Manage network packet filter rules

## Requirements
- [`iptables`](https://manpages.ubuntu.com/manpages/precise/en/man8/iptables.8.html) (command line tool)

## Attributes

| Name               | Type   | Description                                                                                     | Mandatory | Default      |
|:-------------------|--------|-------------------------------------------------------------------------------------------------|-----------|--------------|
| `command`          | `str`  | Which command should be run. Depending on the choice different attributes are accepted          | Yes       | -            |
| `table`            | `str`  | Table to operate on                                                                             | No        | `"filter"`   |
| `chain`            | `str`  | Chain to operate on. `"ALL"` can be used in commands like flush, to flush all chains of a table | No        | -            |
| `protocol`         | `str`  | Protocol to be used                                                                             | No        | -            |
| `destination_port` | `int`  | Tcp/udp network port                                                                            | No        | -            |
| `source`           | `str`  | Source IP of incoming traffic                                                                   | No        | -            |
| `priority`         | `int`  | Number signifing priority for rule                                                              | No        | `0`          |
| `target`           | `str`  | Target for packet if the rule matches                                                           | No        | -            |
| `rules`            | `data` | Data of rules provided to command `exclusive` to keep while removing all others                 | No        | -            |
| `executable`       | `str`  | Path to `iptables` executable                                                                   | No        | `"iptables"` |

## Command Validation

| *Command\Valid Attribute* | **table** | **chain** | **protocol** | **destination_port** | **source** | **priority** | **target** | **rules** | **executable** |
| ------------------------- | --------- | --------- | ------------ | -------------------- | ---------- | ------------ | ---------- | --------- | -------------- |
| **append**                | Yes       | Yes       | Yes          | Yes                  | Yes        | No           | Yes        | No        | Yes            |
| **insert**                | Yes       | Yes       | Yes          | Yes                  | Yes        | Yes          | Yes        | No        | Yes            |
| **delete**                | Yes       | Yes       | Yes          | Yes                  | Yes        | No           | Yes        | No        | Yes            |
| **flush**                 | Yes       | Yes       | No           | No                   | No         | No           | No         | No        | Yes            |
| **policy**                | Yes       | Yes       | No           | No                   | No         | No           | Yes        | No        | Yes            |
| **exclusive**             | Yes       | Yes       | No           | No                   | No         | No           | No         | Yes       | Yes            |

Its important to note that some attributes have their own validation requirements. For example `destination_port` should expect `protocol` to be present.

## Examples

### Append rule to accept traffic from some IP

```cfengine3
bundle agent main
{
  iptables:
      "accept_cfengine_com"
        command => "append",
        chain => "INPUT",
        source => "34.107.174.45",
        target => "ACCEPT";
}
```

### Append a rule to drop traffic from telnet port

```cfengine3
bundle agent main
{
  iptables:
      "drop_telnet"
        command => "append",
        chain => "INPUT",
        protocol => "tcp",
        destination_port => 23,
        target => "DROP";
}
```

### Insert a rule to accept ssh port with high priority

```cfengine3
bundle agent main
{
  iptables:
      "accept_ssh"
        command => "insert",
        chain => "INPUT",
        protocol => "tcp",
        destination_port => 22,
        priority => 1,
        target => "ACCEPT";
}
```

### Delete a rule that accepts traffic from some IP

```cfengine3
bundle agent main
{
  iptables:
      "delete_accept_cfengine_com"
        command => "delete",
        chain => "INPUT",
        source => "34.107.174.45",
        target => "ACCEPT";
}
```

### Set an aggressive policy for incoming traffic

```cfengine3
bundle agent main
{
  iptables:
      "aggressive_policy"
        command => "policy",
        chain => "INPUT",
        target => "DROP";
}
```

### Flush a specific filter chain

Flushing chains should be done primarily when the chains are _expected_ to stay flushed.

``` cfengine3
bundle agent main
{
  iptables:
      "flush_INPUT"
        command => "flush",
        chain => "INPUT";
}
```

### Flush all filter chains

```cfengine3
bundle agent main
{
  iptables:
      "flush_all"
        command => "flush",
        chain => "ALL";
}
```

### Ensure only specific rules are present

To maintain a consistent state in a chain without involving flush, a dictionary of rules can be provided to command `exclusive`. It should be noted that some level of coordination is required for the rules per dictionary. As seen below, a simple practice is to put rules of the same `table` _and_ `chain` together.

```cfengine3
bundle common allow_cfengine_and_ssh
{
  vars:
      "rules" data => '{
        "table": "filter",
        "chain": "INPUT",
        "rule_specs": {
          "accept_cfengine": {
            "source": "34.107.174.45",
            "priority": -1,
            "target": "ACCEPT"
          },
          "accept_ssh": {
            "protocol": "tcp",
            "destination_port": 22,
            "priority": 4,
            "target": "ACCEPT"
          },
        }
    }';
}

bundle agent main
{
  iptables:
      "clean_non_cfengine_rules"
        command => "exclusive",
        chain => "${allow_cfengine_and_ssh.rules[table]}",
        rules => @{allow_cfengine_and_ssh.rules};
}
```

### Total CFEngine control

```cfengine3
bundle common allow_incoming_cfengine
{
  vars:
      "rules" data => '{
        "table": "filter",
        "chain": "INPUT",
        "rule_specs": {
          "accept_cfe_port": {
            "protocol": "tcp",
            "destination_port": 5308,
            "priority": 1,
            "target": "ACCEPT"
          },
          "accept_ssh": {
            "protocol": "tcp",
            "destination_port": 22,
            "priority": 4,
            "target": "ACCEPT"
          },
        }
      }';
}

bundle agent main
{
  vars:
      "rules" data => @{allow_incoming_cfengine.rules};
      "accept_cfe_port" data => @{rules[rule_specs][accept_cfe_port]};
      "accept_ssh" data => @{rules[rule_specs][accept_ssh]};

  iptables:
      "clean_non_cfengine_rules"
        command => "exclusive",
        chain => "${rules[chain]}",
        rules => @{rules};

      "aggressive_policy"
        command => "policy",
        chain => "INPUT",
        target => "DROP";

      "accept_cfengine_port"
        command => "insert",
        table => "${rules[table]}",
        chain => "${rules[chain]}",
        protocol => "${accept_cfe_port[protocol]}",
        destination_port => "${accept_cfe_port[destination_port]}",
        priority => "${accept_cfe_port[priority]}",
        target => "${accept_cfe_port[target]}";

      "accept_ssh"
        command => "insert",
        table => "${rules[table]}",
        chain => "${rules[chain]}",
        protocol => "${accept_ssh[protocol]}",
        destination_port => "${accept_ssh[destination_port]}",
        priority => "${accept_ssh[priority]}",
        target => "${accept_ssh[target]}";

  reports:
      "--- ${this.bundle} ---";
}
```

## Notes

All rules added by the iptables custom promise will have a comment signifing its priority. The `-m comment --comment` match will be used with iptables. The comment follows the pattern `CF3:priority:X` where `X` is `-1` or `>=1`. That comment will be used as key for any sorting/manipulating of the rules in a chain when evaluating the append/insert promises. Keeping a promise means that the rule was already inserted at the proper chain region according to its priority. Repairing a promise means changing the iptables rules, for example by inserting, removing, or moving a rule in the chain. If multiple rules have the same priority they the will be inserted one after the other making a block of same priority rules. Pedantically it should be noted that if two rules differ only in their priority they are _not_ the same rule.

## Authors

This software was created by the team at [Northern.tech AS](https://northern.tech), with many contributions from the community. Thanks everyone!

[CFEngine](https://cfengine.com) is sponsored by [Northern.tech AS](https://northern.tech)

## Contribute

Feel free to open pull requests to expand this documentation, add features or fix problems.
You can also pick up an existing task or file an issue in [our bug tracker](https://tracker.mender.io/issues/).

## License

This software is licensed under the MIT License. See LICENSE in the root of the repository for the full license text.
