# http promise type

## Synopsis

* *Name*: `http`
* *Version*: `0.0.1`
* *Description*: Perform HTTP requests from policy.

## Requirements

* git (the command line tool)

## Attributes

| Name            | Type      | Description                                              | Mandatory | Default  |
| --------------- | --------- | -------------------------------------------------------- | --------- | -------- |
| `file`          | `string`  | File system path for where to save the response (body).  | No        | -        |

## Examples

Check out a git repository in a given destination path:

```cfengine3
bundle agent __main__
{
  http:
      "https://cfengine.com/images/cfengine-logo.svg"
        file => "/var/cfengine/cfengine-logo.svg",
        if => not(fileexists("/var/cfengine/cfengine-logo.svg"));
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
