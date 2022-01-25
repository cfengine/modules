# groups promise type

## Synopsis

* *Name*: `groups`
* *Version*: `0.1.2`
* *Description*: Manage local groups.
* *Note*: This is an experimental version of a promise type, and may be changed in the future.

## Requirements

* Unix-like system.

## Attributes

| Name      | Type                        | Description                                                                                     | Mandatory | Default |
| --------- | --------------------------- | ----------------------------------------------------------------------------------------------- | --------- | ------- |
| `policy`  | `string`                    | Whether group should be present or absent on the local host                                     | no        | present |
| `members` | `string` / `data` / `body`  | JSON string / data container / custom body containing attributes "include", "exclude" & "only"  | no        | -       |
| `gid`     | `integer`                   | The GID of the group                                                                            | no        | -       |

## Examples

Present group `foo` including user `alice` and `bob`, but excluding user `malcom`:

```
@if minimum_version(3.20)
body members foo
{
  include => { "alice", "bob" };
  exclude => { "malcom" };
}
@endif

bundle agent main
{
  groups:
      "foo"
        policy => "present",
@if minimum_version(3.20)
        members => foo;
@else
        members => '{ "include": ["alice", "bob"],
                      "exclude": ["malcom"] }';
@endif
}
```

Present group `bar` with GID `123` including only user `alice`:

```
@if minimum_version(3.20)
body members bar
{
  only => { "alice" };
}
@endif

bundle agent main
{
  groups:
      "bar"
@if minimum_version(3.20)
        members => bar,
@else
        members => '{ "only": ["alice"] }',
@endif
        gid = 123;
}
```

Absent group `baz`:

```
bundle agent main
{
  groups:
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
