This is an experimental module for both uninstalling and installing packages based on conditions (CFEngine class expressions).
Users can specify a list of packages which should be uninstalled by default, and some packages which should be installed under certain conditions.
With this logic, you can have a long list of packages which are generally not allowed, and then for some of them, specify the exact scenarios where they are allowed.
This module uses the system package manager (via packages promises) to both install and uninstall packages.

**Example:** For security reasons, you want to uninstall `talk`, `samba` and `apache2` in your infrastructure.
On your webservers, which have the `webserver` CFEngine class, you want Apache to be installed.
In this module, you put `talk,samba,apache2` in the list of packages to uninstall, and in the list of packages to install you put `apache2` with the condition `webserver`.
The module will install `apache2` on your webservers and uninstall it everywhere else.
`talk` and `samba` will be uninstalled everywhere.
As always with CFEngine, if the state is already correct, if the packages are already installed / not installed, no actions will be performed.

**Hint:** Package names are based on your system's package manager.
In the list of packages to uninstall, it is convenient to just name all the variants of the name, for example `httpd` for RHEL and `apache2` for Debian-based systems.
For the packages to install you have to be more careful; when package names are different use the platform as part of the condition and the correct package name for that platform.
For our example above, it could be install `apache2` with the condition `webserver&debian`, and another entry to install `httpd` with the condition `webserver&redhat`.

**Note:** This module is experimental, and things might change.
Specifically the module input currently accepts strings with comma separated package names.
We might change this to lists of strings and also try out different ways to specify input.
Feel free to play with it and give us feedback, but maybe don't use it for important infrastructure, yet.

**Warning:** If using the same packages in both lists of packages to install and uninstall, be careful with how you specify the condition.
In general, you want the condition to be very stable (not varying over time) - when the condition is true the package will be installed and when false, the package is uninstalled.
If you use time-based classes or other conditions which vary, you can end up in a situation where you install and uninstall the package over and over again.
