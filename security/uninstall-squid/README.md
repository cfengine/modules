The [Squid](https://en.wikipedia.org/wiki/Squid_%28software%29) software is used for proxying and caching requests (HTTP, FTP, DNS, etc.).
To reduce attack surface, it is recommended to uninstall squid when it is not needed.

**Recommendation:** Uninstall Squid by default / where it is not needed, ensuring it won't be used by malicious attackers.
If Squid is needed on some machines, explicitly define what hosts should have it installed.

## Example

If you try installing the package and running the agent with this module, you should see it get uninstalled:

```
$ apt install squid
$ cf-agent -KI
    info: Successfully removed package 'squid'
```

## Adding exceptions

If this package is really needed on some hosts, you can add an exception with the `exception_uninstall_squid` class.
This class can be set within `def.json` ([Augments](https://docs.cfengine.com/docs/master/reference-language-concepts-augments.html)), from policy, or in the **Host specific data** section in host info pages inside Mission Portal, the CFEngine Enterprise Web UI.
