The Apache web server, `httpd`, allows you to host websites and files.
To reduce attack surface, it's generally recommended to not run it and uninstall it where it's not needed.
A web server which is "accidentally" running, could help an attacker get into the system, especially if it is running an older version or lacks proper security configuration.

**Recommendation:** Ensure the Apache web server is only running where necessary, by uninstalling it on all other machines (by default).
Explicitly specify which machines are allowed to run the web server.

## Example

If you try installing the package and running the agent with this module, you should see it get uninstalled:

```
$ yum install httpd
$ cf-agent -KI
    info: Successfully removed package 'httpd'
```

## Adding exceptions

When you need to run the Apache web server on some hosts, you can add an exception with the `exception_uninstall_apache` class.
This class can be set within `def.json` ([Augments](https://docs.cfengine.com/docs/master/reference-language-concepts-augments.html)), from policy, or in the **Host specific data** section in host info pages inside Mission Portal, the CFEngine Enterprise Web UI.
