The [Samba](https://en.wikipedia.org/wiki/Samba_%28software%29) software enables file and printer sharing and is commonly used in mixed Windows and Linux environments.
To reduce attack surface, you should uninstall samba where it is not needed, for example if you are using other software for file sharing.

**Recommendation:** Uninstall Samba when possible (when it is not needed).
For infrastructures or environments which don't use it at all, uninstall it everywhere.
If some of your hosts need to use it, explicitly define where it is needed, and uninstall it everywhere else.

## Example

If you try installing the package and running the agent with this module, you should see it get uninstalled:

```
$ yum install samba
$ cf-agent -KI
    info: Successfully removed package 'samba'
```

## Adding exceptions

If this package is really needed on some hosts, you can add an exception with the `exception_uninstall_samba` class.
This class can be set within `def.json` ([Augments](https://docs.cfengine.com/docs/master/reference-language-concepts-augments.html)), from policy, or in the **Host specific data** section in host info pages inside Mission Portal, the CFEngine Enterprise Web UI.
