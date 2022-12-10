The `cron` utility enables running commands or programs periodically.
System-wide `cron`-related configuration files exist in the `/etc` directory.
For these files, enforcing strict access is essential, as editing them allows you to run commands as any user, including `root`. 

**Recommendation:** Limit access to the various `cron`-related files and directories in `/etc`.
All of them should be owned by `root` and have group set to `root` as well.
For the directories, permissions should be `0700`.
The `/etc/crontab` file should have permissions `0600`, and `/etc/cron.allow` can have slightly less restrictive permissions, `0640`.
This module continuosly enforces owners, groups and permission bits on all of these files and directories.
On a single machine, you can also set this from the command line:

```
$ sudo chown root /etc/cron.allow
$ sudo chgrp root /etc/cron.allow
$ sudo chmod 0640 /etc/cron.allow
$ sudo chown root /etc/crontab
$ sudo chgrp root /etc/crontab
$ sudo chmod 0600 /etc/crontab
$ sudo chown root /etc/cron.d
$ sudo chgrp root /etc/cron.d
$ sudo chmod 0700 /etc/cron.d
$ sudo chown root /etc/cron.hourly
$ sudo chgrp root /etc/cron.hourly
$ sudo chmod 0700 /etc/cron.hourly
$ sudo chown root /etc/cron.daily
$ sudo chgrp root /etc/cron.daily
$ sudo chmod 0700 /etc/cron.daily
$ sudo chown root /etc/cron.weekly
$ sudo chgrp root /etc/cron.weekly
$ sudo chmod 0700 /etc/cron.weekly
$ sudo chown root /etc/cron.monthly
$ sudo chgrp root /etc/cron.monthly
$ sudo chmod 0700 /etc/cron.monthly
```

## Example

If you modify one of these files and run the agent with this module, you should see it fixed:

```
$ chmod 0777 /etc/cron.d
$ cf-agent -KI
    info: Object '/etc/cron.d' had permissions 0777, changed it to 0700
```
