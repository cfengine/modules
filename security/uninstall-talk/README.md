The `talk` program allowed users on early unix systems in the 80's and 90's to chat with each other.
As it does not encrypt communication, and has been proven vulnerable in several ways, its use today is discouraged.

**Recommendation:** Do not use `talk` as it is insecure (provides no encryption for communication).
Uninstall both `talk` and `talk-server`, and ensure it isn't used / installed in your infrastructure.
This module provides an easy way to achieve this.

## Example

If you try installing the package(s) and running the agent with this module, you should see it get uninstalled:

```
$ sudo apt install talk
$ cf-agent -KI
    info: Successfully removed package 'talk'
```

## Adding exceptions

If this package is really needed on some hosts, you can add an exception with the `exception_uninstall_talk` class.
This class can be set from the **Host specific data** section in host info pages inside Mission Portal, the CFEngine Enterprise Web UI.
