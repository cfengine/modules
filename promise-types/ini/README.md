# Ansible INI promise type

## Synopsis

* *Name*: `Ansible INI - Custom Promise Module`
* *Version*: `0.0.1`
* *Description*: Manage configuration files through the Ansible INI module in CFEngine.

## Requirements

* Python installed on the system
* `ansible` pip package
* Correct path to the `ini_file.py` in the custom promise module

## Attributes

See [anible_ini module](https://docs.ansible.com/ansible/latest/collections/community/general/ini_file_module.html).

## Example

```cfengine3
bundle agent main
{
  ini:
    "/path/to/file.ini"
        section => "foo",
        option  => "bar",
        value   => "baz";
}
```
