A lot of software is still available to install in package managers, but not recommended to use for security reasons.
Old and unmaintained software often has bugs, security vulnerabilities or lack important security features such as strong authentication and encryption.
Different compliance frameworks and security hardening guidelines recommend uninstalling various packages, such as:

* `bind`
* `dhcp` / `isc-dhcp-server`
* `dovecot` / `dovecot-core`
* `httpd` / `apache2`
* `samba`
* `squid`
* `talk` / `talk-server` / `talkd`
* `telnet-server` / `telnetd`
* `xinetd`

**Recommendation:** Uninstall packages you don't need, especially focusing on servers / daemons, and software known to be insecure or have vulnerabilities.
Use this module and specify the packages you want uninstalled with module input.
Compliance frameworks and security hardening guidelines can help you with ideas beyond the list above.

**Hint:** With this module, you don't have to worry about uninstalling the "right" package name according to the platform.
Just add all the names you want uninstalled, if the package is not found, CFEngine considers it not installed.
As an example, in RHEL / yum, the Dovecot software is in a package called `dovecot`, while on Ubuntu / apt, the equivalent package name is `dovecot-core`.
If you want Dovecot uninstalled, and you use both RHEL and Ubuntu system, just add both `dovecot` and `dovecot-core` to the list of packages to uninstall.
