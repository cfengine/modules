Promise type for asserting facts about system state.

Unlike other promise types, `assert:` promises never change anything. Evaluation only checks whether something is already true, and reports `PASS` or `FAIL` accordingly, with a comparison of what was expected against what was actually found.

## Promiser

A short, descriptive name for the assertion, e.g. `"apache is listening on port 80"`. Used for logging each assertion.

## Attributes

Each `assert:` promise needs exactly one subject attribute, and at least one check attribute (except `command`, which can stand alone and only checks that the command exits zero) -- or no subject at all, see [No subject: gating on `if`/`unless`](#no-subject-gating-on-ifunless).

| Subject   | Type             | Checks                                     | Description                             |
| --------- | ---------------- | ------------------------------------------ | --------------------------------------- |
| `int`     | `string`         | `equals`, `greater_than`, `less_than`      | A whole number                          |
| `real`    | `string`         | `equals`, `greater_than`, `less_than`      | A number, whole or fractional           |
| `str`     | `string`         | `equals`, `not_equals`, `contains`         | A string                                |
| `file`    | `string`         | `exists`, `perms`, `contents`              | Path to a file                          |
| `dir`     | `string`         | `exists`                                   | Path to a directory                     |
| `command` | `string`         | `output`                                   | A shell command, run to check its result|
| `slist`   | `slist`          | `equals`, `contains`                       | A list of strings                       |
| `ilist`   | `ilist`          | `equals`, `contains`                       | A list of whole numbers                 |
| `rlist`   | `rlist`          | `equals`, `contains`                       | A list of numbers                       |

| Check          | Type     | Applies to                         | Description                                                 |
| -------------- | -------- | ---------------------------------- | ------------------------------------------------------      |
| `equals`       | *        | `int`, `real`, `str`, `*list`      | Subject equals this value                                   |
| `not_equals`   | `string` | `str`                              | Subject does not equal this value                           |
| `greater_than` | `string` | `int`, `real`                      | Subject is greater than this value                          |
| `less_than`    | `string` | `int`, `real`                      | Subject is less than this value                             |
| `contains`     | *        | `str`, `*list`                     | Subject contains this substring/element, or (for `*list`) all elements of this list |
| `exists`       | `string` | `file`, `dir`                      | `"true"` or `"false"`: whether the path exists              |
| `perms`        | `string` | `file`                             | Permission bits the file must have, e.g. `"0644"`           |
| `contents`     | `string` | `file`                             | The file's exact contents                                   |
| `output`       | `string` | `command`                          | Substring the command's combined stdout+stderr must contain |

Giving `equals` for an `*list` subject requires the matching list type of the same shape (`@(variable)` or an inline `{ ... }`), not a bare scalar cf-agent doesn't type-check custom promise attributes, so a wrong-typed value could otherwise misbehave silently instead of failing clearly.

### Numeric comparisons

`int`/`real` values and `ilist`/`rlist` elements are parsed as floats first, since CFEngine's own numeric functions (e.g. `eval()`) return whole numbers as strings like `"7.000000"`; `int`/`ilist` additionally reject a non-whole value and convert it to an int. This means `ilist`/`rlist` elements compare numerically, not as raw strings, so `"2"` and `"2.000000"` are the same value; `slist` elements compare as-is.

### List `contains`

For an `*list` subject, `contains` takes either a single value (checks for that one element) or a list (checks that every element of it is present). A failing list check reports only the missing element(s).

## No subject: gating on `if`/`unless`

A promise with no subject attribute passes by default -- useful for asserting a class or variable directly with CFEngine's own `if`/`unless`, rather than one of the subjects above. `pass => "false"` inverts it.

Since `if`/`unless` make cf-agent skip the promise entirely when unmet, this only reports a result when the condition *is* met -- there's no signal for the unmet case:

```cfengine3
assert:
  "sum is defined"
    if => isvariable("sum"); # passes, skipped if sum isn't defined

  "my_class must not be set"
    pass => "false",
    if => "my_class"; # fails only if my_class is set
```

## Example

```cfengine3
bundle agent main
{
  vars:
    "ports" ilist => { "22", "80", "443" };

  assert:
    "agent version is current"
      int    => "$(sys.cf_version_major)",
      equals => "3";

    "port 80 open"
      ilist    => "@(ports)",
      contains => "80";

    "expected ports are open"
      ilist    => "@(ports)",
      contains => {22, 80, 9090};

    "config file exists"
      file   => "/etc/myapp/config.yaml",
      exists => "true";

    "config file has the right owner-only permissions"
      file  => "/etc/myapp/config.yaml",
      perms => "0600";

    "service responds on its health check"
      command => "curl -fs http://localhost:8080/health",
      output  => "ok";
}
```

A failing assertion reports what was expected and what was actually found, e.g.:

```
FAIL expected ports are open # [22, 80, 443] does not contain [9090]
```

## Limitations

- `command`'s `output` check matches a substring against the command's combined stdout and stderr; it doesn't support matching stdout and stderr separately, or exact-match semantics.
- `contains` has no "any of" mode for lists, only "one of" (a single value) or "all of" (a list).

## Authors

This software was created by the team at [Northern.tech](https://northern.tech), with many contributions from the community.
Thanks everyone!

## Contribute

Feel free to open pull requests to expand this documentation, add features, or fix problems.
You can also pick up an existing task or file an issue in [our bug tracker](https://northerntech.atlassian.net/).

## License

This software is licensed under the MIT License. See LICENSE in the root of the repository for the full license text.
