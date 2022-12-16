The [Extended Internet Service Daemon](https://en.wikipedia.org/wiki/Xinetd), `xinetd`, allows you to start services on request.
This can be useful, allowing you to host many different network based services, while `xinetd` is the only daemon running.
When a network request arrives, `xinetd` determines which service to start and relay the request to.
If this kind of functionailty is not needed, it is recommended to uninstall it.
An alternative to `xinetd` is [`systemd`](https://en.wikipedia.org/wiki/Systemd), with the socket activation feature.
Since most Linux systems use `systemd` already, you don't have to install and rely on an extra piece of software, if you use that. 

**Recommendation:** Uninstall `xinetd` (by default) wherever it is not needed.
If some hosts need to use `xinetd`, explicitly define them.
Consider using `systemd` socket activation instead of `xinetd`.

## Example

If you try installing the package(s) and running the agent with this module, you should see it get uninstalled:

```
$ apt install xinetd
$ cf-agent -KI
    info: Successfully removed package 'xinetd'
```

## Adding exceptions

If this package is really needed on some hosts, you can add an exception with the `exception_uninstall_xinetd` class.
This class can be set within `def.json` ([Augments](https://docs.cfengine.com/docs/master/reference-language-concepts-augments.html)), from policy, or in the **Host specific data** section in host info pages inside Mission Portal, the CFEngine Enterprise Web UI.
