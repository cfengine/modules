[Host-based authentication with ~/.shosts](https://en.wikibooks.org/wiki/OpenSSH/Cookbook/Host-based_Authentication) is the equivalent to `/etc/ssh/.shosts.equiv`.
It allows individual users to define a list of trusted remote machines, or user-machine pairs, which are allowed to try host-based authentication.

However a global `.shosts.equiv` is preferable to having `.shosts` in each and every home directory.

****Recommendation:**** Do not use user defined host based authentication. Use this `delete-home-dotshosts` module to inventory and delete `~/.shosts` files. This ensures you are protected in the future, if somebody adds a `~/.shosts` file.

## Inventory

With Mission Portal you can find hosts which have `~/.shosts` files and details about reasons for exception:

[![Inventory Report showing found ~/.shosts and Exception](https://raw.githubusercontent.com/cfengine/modules/master/security/delete-home-dotshosts/media/inventory-report.png)](https://raw.githubusercontent.com/cfengine/modules/master/security/delete-home-dotshosts/media/inventory-report.png)

## Example

If you try creating a `~/.shosts` file running the agent with this module, you should see it get removed:

Example output with an exception present:

```
$ sudo touch /root/.shosts /home/vagrant/.shosts
# sudo cf-agent -KI
R: Found /home/vagrant/.shosts, /root/.shosts, but not removing because of exception: I got an exception for .shosts from the security czar. See JIRA-1234 for more info.
```

Example output without exception present:

```
$ sudo cf-agent -KI
    info: Deleted file '/home/vagrant/.shosts'
    info: Deleted file '/root/.shosts'
```

## Configuration

### Specifying home directory roots to search

In [augments](https://docs.cfengine.com/docs/master/reference-language-concepts-augments.html#top) define a [variable](https://docs.cfengine.com/docs/master/reference-language-concepts-variables.html) `delete_home_dotshosts:main.home_dir_roots` as a list or data container array with each element being a home directory root to search.

### Adding exceptions

If `~/.shosts` files are really needed on some hosts, you can add an exception in one of two ways:

* Define the `exception_delete_home_dotshosts` class.
* Define the `delete_home_dotshosts:main.exception` variable as a string with the reason for the exception as its value.

Functionally, they do the same, but the variable allows you to list the reasons for exceptions in an **Inventory report** (as seen above).
This can be done from the **Host specific data** section in host info pages inside Mission Portal, the CFEngine Enterprise Web UI.
Here is an example of setting the variable:

[![Host specific data UI, setting the variable delete_home_dotshosts:main.exception](https://raw.githubusercontent.com/cfengine/modules/master/security/delete-home-dotshosts/media/host-specific-data.png)](https://raw.githubusercontent.com/cfengine/modules/master/security/delete-home-dotshosts/media/host-specific-data.png)
