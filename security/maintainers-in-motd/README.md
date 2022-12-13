When using a system it is helpful to know who is responsible for managing the system specifically.

Adding maintainer contact and purpose information as part of `/etc/motd` is a helpful reminder to all users about what to use the host for and who to contact in case of questions or issues.

This information can be added in Mission Portal host info page as follows:

![Configuring host maintainer](https://raw.githubusercontent.com/cfengine/modules/master/security/maintainers-in-motd/host-specific-data.png)

## Example

On running the agent for the first time:

```sh
    info: Replaced pattern '^(?!\:\:\:\ use\ this\ machine\ for\ CFEngine\ personal\ hub\,\ contact\ Craig\ Comstock\(craig\.comstock\@somewhere\)\ with\ any\ questions\/issues\.\ \:\:\:$):::.*:::$' in '/etc/motd'                                                                                                                       
    info: replace_patterns promise '^(?!\:\:\:\ use\ this\ machine\ for\ CFEngine\ personal\ hub\,\ contact\ Craig\ Comstock\(craig\.comstock\@somewhere\)\ with\ any\ questions\/issues\.\ \:\:\:$):::.*:::$' repaired                                                                                                                     
    info: Edited file '/etc/motd'
```

On subsequent runs if the maintainer or purpose information changes, that one line will change appropriately.
