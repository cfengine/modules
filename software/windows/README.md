The `windows-openssh-server` bundle ensures that an openssh server is running on Windows hosts if the class data:openssh_server_installed is defined.

You can define this in the Host Info page or CMDB.

This bundle depends on and uses the [windows-capability](https://build.cfengine.com/modules/windows-capability/) module to accomplish the goal.
