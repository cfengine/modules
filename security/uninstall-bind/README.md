The `bind` package provides the `named` service, for running a DNS server.
Most machines are not DNS servers, and don't need this package.
To reduce attack surface, this package should be uninstalled when not necessary. 

**Recommendation:** Ensure only DNS servers use the `bind` package by uninstalling it on all other hosts (by default).
Explicitly define hosts which are DNS servers and thus need the `bind` package.

## Example

If you try installing the package and running the agent with this module, you should see it get uninstalled:

```
$ yum install bind
$ cf-agent -KI
    info: Successfully removed package 'bind'
```

**Hint:** On Debian / `apt`-based machines, the package is sometimes called `bind9`.

## Adding exceptions

If this package is really needed on some hosts, you can add an exception with the `exception_uninstall_bind` class.
This class can be set within `def.json` ([Augments](https://docs.cfengine.com/docs/master/reference-language-concepts-augments.html)), from policy, or in the **Host specific data** section in host info pages inside Mission Portal, the CFEngine Enterprise Web UI.
