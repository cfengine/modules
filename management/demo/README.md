# demo - Functionality useful for CFEngine demo setups

**This module is for demoing purposes and uses insecure settings - do not use in production environments.**

This module provides roughly the same functionality as installing CFEngine with cf-remote's `--demo` option:

* Sets the ACL's for who is allowed to connect / bootstrap to wide open on both IPv4 and IPv6
* Makes CFEngine's policy fetching, evaulation and reporting happen every minute
* Enables monitoring for everything for both hubs and clients
* Enables the autorun functionality
* Enables automatic installation of Federeated Reporting Dependencies
* Enables purging of files from `inputs` (when they no longer exist in `masterfiles`)
* Enable automatic restart of CFEngine daemons when configuration changes
