The `git` promise type enables writing concise policy for cloning a git repo and keeping it updated.

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

## Authentication

This module will set the `HOME` environment variable if it is not set already based on the user running `cf-agent`, typically `root`.

In order to add authentication you can use [gitcredentials](https://git-scm.com/docs/gitcredentials).

An example of this usage would be to have two files in `$HOME`: `.gitconfig` and `.git-credentials`.

- `.gitconfig`
```sh
[credential]
    helper = store
```

- `.git-credentials`

Using the `store` helper places the username and password in plaintext in `$HOME/.git-credentials`.

Here is an explanation of that file [storage format](https://git-scm.com/docs/git-credential-store#_storage_format):

> The `.git-credentials` file is stored in plaintext. Each credential is stored on its own line as a URL like:

```text
https://user:pass@example.com
```
> No other kinds of lines (e.g. empty lines or comment lines) are allowed in the file, even though some may be silently ignored. Do not view or edit the file with editors.

## Authors

This software was created by the team at [Northern.tech](https://northern.tech), with many contributions from the community.
Thanks everyone!

## Contribute

Feel free to open pull requests to expand this documentation, add features or fix problems.
You can also pick up an existing task or file an issue in [our bug tracker](https://tracker.mender.io/issues/).

## License

This software is licensed under the MIT License. See LICENSE in the root of the repository for the full license text.
