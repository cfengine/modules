Promise type for manipulating `json` files

## Attributes

| Name        | Type             | Description                                                                   |
| ----------- | ---------------- | ----------------------------------------------------------------------------- |
| `object`    | `data container` | json object type. It can also be json arrays                                  |
| `array`     | `data array`     | json array type                                                               |
| `string`    | `string`         | json string type                                                              |
| `number`    | `real`, `int`    | json number type                                                              |
| `primitive` | `string`         | Primitives are values that are either `"true"`, `"false"` or `"null"` in json |

## Examples

### Write to a whole file

To write to a json file, you can do:

```cfengine3
bundle agent main
{
  json:
    "/tmp/newfile.json"
      array => '["hello", "world"]';
}
```

The resulting `/tmp/newfile.json` will only contain the array:

```json
["hello", "world"]
```

If the `/tmp/newfile.json` doesn't exist, it will be created. If it exists and contains some data, they will be overwritten.

### Write to a specific field

Given a json file `/tmp/oldfile.json`,

```json
{
  "foo": "bar"
}
```

we can modify/append a field by doing:

```cfengine3
bundle agent main
{
  json:
    "/tmp/oldfile.json:greeting"
      array => '["hello", "world"]';
}
```

And the content of `/tmp/oldfile.json` will become:

```json
{
  "foo": "bar",
  "greeting": ["hello", "world"]
}
```

If the field doesn't exist, it is appended. If it already exists, its data will be overwritten.

### Writing arrays

In order to write compound type such as arrays containg booleans, numbers, etc... One has to use the `data` type in the policy.

To see what happens if we use

```cfengine3
bundle agent main
{
  vars:
    "json_data"
      data => '[1.2, true, "hello!"]';

    "real_list"
      rlist => {"1.2", "2.3"};
    "bool_list"
      slist => {"true", "false"};

  json:
    "/tmp/example_1.json:json_data"
      array => "@(json_data)";

    "/tmp/example_2.json:real_list"
      array => "@(real_list)";
    "/tmp/example_2.json:bool_list"
      array => "@(bool_list)";
}
```

We can compare the content of `/tmp/example_1.json` and `/tmp/example_2.json`:

```json
{
  "json_data": [1.2, true, "hello!"]
}
```

```json
{
  "real_list": ["1.2", "2.3"],
  "bool_list": ["true", "false"]
}
```

As we can see, using slist, rlist or ilist to write arrays will always result in array of strings. If we want more complex arrays using containg number, true, false or null, then we need to use the `data container` type.

## Not implemented yet

The copy attribute allows to copy the content of a json file into another json file. For example, `/tmp/oldfile.json` contains the following:

```json
{
  "hello": "world"
}
```

We can copy it into the `/tmp/newfile.json` in the field `"oldfile"` by doing:

```cfengine3
bundle agent main
{
  json:
    "/tmp/newfile.json:oldfile"
      copy => "/tmp/oldfile.json";
}
```

```json
{
  "oldfile": {
    "hello": "world"
  }
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
