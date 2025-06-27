The `symlink` promise type enables concise policy for symbolic links.

## Attributes

| Name          | Type          | Description                                               | Default       |
|---------------|---------------|-----------------------------------------------------------|---------------|
| `file`        | `string`      | Path to file. Cannot be used together with `directory`.   | -             |
| `directory`   | `string`      | Path to directory. Cannot be used together with `file`.   | -             |

## Examples

To create a symlink to the directory `/tmp/my-dir` with the name `/tmp/my-link`, we can do:

```cfengine3
bundle agent main
{
  symlinks:
    "/tmp/my-link"
      directory => "/tmp/my-dir";
}
```

In similar fashion, to create a symlink to the file `/tmp/my-dir` with the name `/tmp/my-link`, we can do:

```cfengine3
bundle agent main
{
  symlinks:
    "/tmp/my-link"
      file => "/tmp/my-file";
}
```

If the path to the file/directory given in the promise is not an absolute, doesn't exist or its type doesn't correspond with the promise's attribute ("file" or "directory"), then the promise will fail.

Trying to symlink to a file/directory where the link name is the same as an existing file/directory will also make the promise fail.

Already exisiting symlinks with incorrect target will be corrected according to the policy.


## Authors

This software was created by the team at [Northern.tech](https://northern.tech), with many contributions from the community.
Thanks everyone!

## Contribute

Feel free to open pull requests to expand this documentation, add features, or fix problems.
You can also pick up an existing task or file an issue in [our bug tracker](https://northerntech.atlassian.net/).

## License

This software is licensed under the MIT License. See LICENSE in the root of the repository for the full license text.
