In unix-like systems the `/etc/motd` file is used to display relevant information to users after logging in.
When a user logs in, it is quite common that they get information about the machine, where to find documentation, who to contact if you need help, etc.
Since users may trust and rely on the information there, it is important to prevent misuse by limiting access.
Possible attack vectors include telling users to run a specific command or give them a wrong (malicious) web address or email address for help.

**Recommendation:** Limit access to `/etc/motd` by setting its owner and group to `root`, and permission bits to `0644`.
This module helps you enforce this across your infrastructure.
On a single machine, you can also set this from the command line:

```
$ sudo chown root /etc/motd
$ sudo chgrp root /etc/motd
$ sudo chmod 0644 /etc/motd
```

## Example

If you modify one of these files and run the agent with this module, you should see it fixed:

```
$ sudo chmod 0777 /etc/motd
$ cf-agent -KI
    info: Object '/etc/motd' had permissions 0777, changed it to 0644
```
