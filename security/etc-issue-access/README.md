In unix-like systems the `/etc/issue` file is used to display relevant information to users before logging in.
Since users may trust and rely on the information there, it is important to prevent misuse by limiting access.
Possible attack vectors include telling users to run a specific command or give them a wrong (malicious) web address or email address for help.

**Recommendation:** Limit access to `/etc/issue` by setting its owner and group to `root`, and permission bits to `0644`.
This module helps you enforce this across your infrastructure.
On a single machine, you can also set this from the command line:

```
$ sudo chown root /etc/issue
$ sudo chgrp root /etc/issue
$ sudo chmod 0644 /etc/issue
```

## Example

If you modify one of these files and run the agent with this module, you should see it fixed:

```
$ sudo chmod 0777 /etc/issue
$ cf-agent -KI
    info: Object '/etc/issue' had permissions 0777, changed it to 0644
```
