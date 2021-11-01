# groups-experimental promise type

## Synopsis

* *Name*: `groups-experimental`
* *Version*: `0.1.1`
* *Description*: Manage local groups.

## Requirements

* Unix-like system.

## Attributes

| Name      | Type      | Description                                                      | Mandatory | Default |
| --------- | --------- | -----------------------------------------------------------------| --------- | ------- |
| `policy`  | `string`  | Whether group should be present or absent on the local host      | No        | present |
| `members` | `string`  | JSON object containing attributes "include", "exclude" & "only"  | no        | -       |
| `gid`     | `integer` | The GID of the group                                             | No        | -       |

## Examples

Present group `foo` including user `alice` and `bob`, but excluding user `malcom`:

```
bundle agent main
{
  groups_experimental:
    "foo"
      policy => "present",
      members => '{ "include": ["alice", "bob"],
                    "exclude": ["malcom"] }';
}
```

Present group `bar` with GID `123` including only user `alice`:

```
bundle agent main
{
  groups_experimental:
    "bar"
      members => '{ "only": ["alice"] }',
      gid = 123;
}
```

Absent group `baz`:

```
bundle agent main
{
  groups_experimental:
    "baz"
      policy => "absent";
}
```

## Authors

This software was created by the team at [Northern.tech AS](https://northern.tech), with many contributions from the community. Thanks everyone!

[CFEngine](https://cfengine.com) is sponsored by [Northern.tech AS](https://northern.tech)

## Contribute

Feel free to open pull requests to expand this documentation, add features or fix problems.
You can also pick up an existing task or file an issue in [our bug tracker](https://tracker.mender.io/issues/).

## License

This software is licensed under the MIT License. See LICENSE in the root of the repository for the full license text.
