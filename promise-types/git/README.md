# git promise type

## Synopsis

* *Name*: `git`
* *Version*: `0.1.2`
* *Description*: Manage git checkouts of repositories to deploy files or software.

## Requirements

* git (the command line tool)

## Attributes

| Name            | Type      | Description                                                                                                             | Mandatory | Default  |
| --------------- | --------- | ----------------------------------------------------------------------------------------------------------------------- | --------- | -------- |
| `destination`   | `string`  | Destination path                                                                                                        | No        | Promiser |
| `repository`    | `string`  | Git repository URL                                                                                                      | Yes       | -        |
| `bare`          | `boolean` | If `true`, clones the repository as bare repository                                                                     | No        | -        |
| `clone`         | `boolean` | If `true`, clones the repository if it doesn't exist at the destination path                                            | No        | -        |
| `depth`         | `integer` | Create a shallow clone with a history truncated to the specified number or revisions. Set to 0 to perform a full clone. | No        | `0`      |
| `executable`    | `string`  | Path to the `git` executable                                                                                            | No        | `git`    |
| `force`         | `boolean` | If `true`, discard any local changes to the repository before updating it                                               | No        | -        |
| `recursive`     | `boolean` | If `true`, use the `--recursive` git option                                                                             | No        | `yes`    |
| `reference`     | `string`  | If set, use the `--reference` git option with the given value                                                           | No        | -        |
| `remote`        | `string`  | Name of the git remote                                                                                                  | No        | `origin` |
| `ssh_executable`| `string`  | Path to the `ssh` executable                                                                                            | No        | `ssh`    |
| `ssh_options`   | `string`  | Additional options for the `git` command, e.g. `-o StrictHostKeyChecking=no`                                            | No        | -        |
| `update`        | `boolean` | If `true`, updates the repository if it already exists at the destination path                                          | No        | -        |
| `version`       | `string`  | The version of the repository to checkout. It can be a branch name, a tag name or a SHA-1 hash.                         | No        | `HEAD`   |

## Examples

Check out a git repository in a given destination path:

```cfengine3
bundle agent main
{
  git:
    "starter_pack_repo"
      repository => "https://github.com/cfengine/starter_pack",
      destination => "/northern.tech/cfengine/starter-pack",
      version => "master";
}
```

Full example with almost all the attributes:

```cfengine3
bundle agent main
{
  git:
    "starter_pack_repo"
      destination => "/northern.tech/cfengine/starter_pack",
      repository => "https://github.com/cfengine/starter_pack",
      bare => "true",
      clone => "true",
      depth => "1",
      executable => "/bin/git",
      force => "true",
      recursive => "true",
      remote => "origin",
      ssh_options => "UserKnownHostsFile=/dev/null",
      update => "true",
      version => "master";
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
