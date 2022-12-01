[Remote shell (`rsh`)](https://en.wikipedia.org/wiki/Remote_Shell) allows you to log in and send commands to another computer over the network.
It is notoriously insecure, sending traffic in an unencrypted manner.
In some implementations of `rsh`, passwords are also sent over the network in plaintext.
`rsh` should no longer be used, as much more secure alternatives exist, such as [`ssh`](https://en.wikipedia.org/wiki/Secure_Shell).

**Recommendation:** Do not have the `rsh-server` module installed on any of the machines in your infrastructure, as it presents a substantial security risk.
Use CFEngine Enterprise's software inventory to verify that it isn't installed anywhere, and this module to enforce it (uninstalling the module if it appears somewhere).
This ensures you are protected in the future, if somebody installs the package on a machine, or if somebody adds a machine with the package installed to the infrastructure. 


## Inventory

With Mission Portal you can find hosts which have `rsh-server` installed with a Custom report using the Report Builder GUI:

![Report Builder to find hosts with rsh-server](https://raw.githubusercontent.com/cfengine/modules/master/security/uninstall-rsh-server/rsh-server-report-builder.png)

Or enter the following query in the Show Query section at the bottom.

```
SELECT Hosts.HostName AS "Host name", Software.SoftwareName AS "Software name", Software.SoftwareVersion AS "Software version", Software.ChangeTimeStamp AS "Change time" FROM Hosts LEFT JOIN Software ON Software.HostKey = Hosts.HostKey WHERE  Software.SoftwareName = 'rsh-server'
```

Run or Save the report and see which hosts in your environment have `rsh-server` installed.

![hosts with rsh-server installed](https://raw.githubusercontent.com/cfengine/modules/master/security/uninstall-rsh-server/hosts-with-rsh-server-installed.png)

## Example

If you try installing the package and running the agent with this module, you should see it get uninstalled:

```
$ sudo apt install rsh-server
$ cf-agent -KI
    info: Successfully removed package 'rsh-server'
```

## Adding exceptions

If this package is really needed on some hosts, you can add an exception with the `exception_uninstall_rsh_server` class.
This class can be set from the **Host specific data** section in host info pages inside Mission Portal, the CFEngine Enterprise Web UI.
