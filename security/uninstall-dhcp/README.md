The DHCP service and protocol are used to automatically assign IP addresses to hosts on a network.
An alternative to DHCP is to manually assign static IP addresses to each host.
In a typical home network, the WiFi router is running a DHCP server.
Most machines in a network do not need to run a DHCP server, so it is recommended to uninstall it in order to reduce attack surface.

**Recommendation:** Ensure only the DHCP server is using the DHCP server software, by uninstalling it everywhere else (by default).
Explicitly define which machine(s) are DHCP servers and thus need to have the DHCP software installed.

## Example

If you try installing the package and running the agent with this module, you should see it get uninstalled:

```
$ yum install dhcp
$ cf-agent -KI
    info: Successfully removed package 'dhcp'
```

**Hint:** On Debian / `apt`-based systems, the package name is `isc-dhcp-server`.

## Adding exceptions

If this package is really needed on some hosts, you can add an exception with the `exception_uninstall_dhcp` class.
This class can be set within `def.json` ([Augments](https://docs.cfengine.com/docs/master/reference-language-concepts-augments.html)), from policy, or in the **Host specific data** section in host info pages inside Mission Portal, the CFEngine Enterprise Web UI.
