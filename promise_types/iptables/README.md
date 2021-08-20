# Iptables Promise Module

## Synopsis
- *Name*: `iptables`
- *Version*: `0.1.1`
- *Description*: Manage network packet filter rules

## Requirements
- [`iptables`](https://manpages.ubuntu.com/manpages/precise/en/man8/iptables.8.html) (command line tool)

## Attributes

| Name        | Type  | Description                                                                                     | Mandatory | Default    |
|:------------|-------|-------------------------------------------------------------------------------------------------|-----------|------------|
| `command`   | `str` | Which command should be run. Depending on the choice different attributes are accepted          | Yes       | -          |
| `table`     | `str` | Table to operate on                                                                             | No        | `"filter"` |
| `chain`     | `str` | Chain to operate on. `"ALL"` can be used in commands like flush, to flush all chains of a table | Yes       | -          |
| `rulenum`   | `int` | Index to put the new rule with `1` meaning it will be inserted at the top                       | No        | `1`        |
| `protocol`  | `str` | Protocol to be used                                                                             | No        | -          |
| `dest_port` | `int` | Tcp/udp network port                                                                            | No        | -          |
| `source_ip` | `str` | Source IP of incoming traffic                                                                   | No        | -          |
| `target`    | `str` | Target for packet if the rule matches                                                           | No        | -          |

## Command Validation

| *Command\Valid Attribute* | **table** | **chain** | **rulenum** | **protocol** | **dest_port** | **source_ip** | **target** |
|---------------------------|-----------|-----------|-------------|--------------|---------------|---------------|------------|
| **append**                | Yes       | Yes       | No          | Yes          | Yes           | Yes           | Yes        |
| **insert**                | Yes       | Yes       | Yes         | Yes          | Yes           | Yes           | Yes        |
| **delete**                | Yes       | Yes       | No          | Yes          | Yes           | Yes           | Yes        |
| **flush**                 | Yes       | Yes       | No          | No           | No            | No            | No         |
| **policy**                | Yes       | Yes       | No          | No           | No            | No            | Yes        |

Its important to note that some attribute have their own validation requirements. For example `dest_port` should expect `protocol` to be present.

## Examples

### Append rule to accept traffic from some IP

```cfengine3
bundle agent main
{
  iptables:
      "accept_cfengine_com"
        command => "append",
        chain => "INPUT",
        source_ip => "34.107.174.45",
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
        dest_port => 23,
        target => "DROP";
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
        source_ip => "34.107.174.45",
        target => "ACCEPT";
}
```

###  Insert a rule to accept ssh port as the first rule

```cfengine3
bundle agent main
{
  iptables:
      "accept_ssh"
        command => "insert",
        chain => "INPUT",
        rulenum => 1,
        protocol => "tcp",
        dest_port => 22,
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

### Accept traffic from CFEngine port, drop everything else

``` cfengine3
bundle agent main
{
  iptables:
      "flush_all"
        command => "flush",
        chain => "ALL";

      "aggressive_policy"
        command => "policy",
        chain => "INPUT",
        target => "DROP";

      "accept_cfengine"
        command => "append",
        chain => "INPUT",
        protocol => "tcp",
        dest_port => 5308,
        target => "ACCEPT";
}
```
## Notes

For appending, inserting and deleting commands the [`iptables --check`](https://manpages.ubuntu.com/manpages/precise/en/man8/iptables.8.html#options) command will run first to ensure that the promise is not kept before executing further commands.  
For example:

``` cfengine3
bundle agent main
{
  iptables:
      "accept_cfengine"
        command => "append",
        chain => "INPUT",
        protocol => "tcp",
        dest_port => 5308,
        target => "ACCEPT",
}
```

The above promises to append the rule `-p tcp --dport 5308 -j ACCEPT` in the chain `INPUT` of the tables `filter`. The promise as a whole can be translated into two commands:

``` shell
iptables -t filter --check INPUT -p tcp --dort 5308 -j ACCEPT  # Check state of promise
if [[ $? != 0 ]]  # Rule not found: promise not kept (yet)
then
    iptables -t filter --append INPUT -p tcp --dport 5308 -j ACCEPT
fi
```

## Authors

This software was created by the team at [Northern.tech AS](https://northern.tech), with many contributions from the community. Thanks everyone!

[CFEngine](https://cfengine.com) is sponsored by [Northern.tech AS](https://northern.tech)

## Contribute

Feel free to open pull requests to expand this documentation, add features or fix problems.
You can also pick up an existing task or file an issue in [our bug tracker](https://tracker.mender.io/issues/).

## License

This software is licensed under the MIT License. See LICENSE in the root of the repository for the full license text.
