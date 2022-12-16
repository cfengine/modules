The [`dovecot`](https://en.wikipedia.org/wiki/Dovecot_%28software%29) software is an open-source IMAP and POP3 server.
Its primary purpose is to act as an email storage server.
As most machines are not email servers, it is recommended to uninstall it when possible, to reduce attack surface.

**Recommendation:** Ensure only the intended machines are running the `dovecot` software, by uninstalling it everywhere else (by default).
Explicitly define which hosts in your infrastructure are email servers and need the `dovecot` software installed.

## Example

If you try installing the package and running the agent with this module, you should see it get uninstalled:

```
$ yum install dovecot
$ cf-agent -KI
    info: Successfully removed package 'dovecot'
```

**Hint:** On Debian / `apt`-based systems, the package name is `dovecot-core`.

## Adding exceptions

If this package is really needed on some hosts, you can add an exception with the `exception_uninstall_dovecot` class.
This class can be set within `def.json` ([Augments](https://docs.cfengine.com/docs/master/reference-language-concepts-augments.html)), from policy, or in the **Host specific data** section in host info pages inside Mission Portal, the CFEngine Enterprise Web UI.
