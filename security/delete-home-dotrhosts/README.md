`~/.rhosts` (in each user's home directory) is the user equivalent of to `/etc/hosts.equiv`. it contains a list of host-user combinations.
If a host-user combination is present in the file the listed user is authorized to log in remotely from the associated host without further authentication.

The global `/etc/hosts.equiv` (controlled by an administrator) is preferable to allowing _any_ user the ability to grant access to other users.

****Recommendation:**** Do not allow user defined host based authentication. Use this `delete-home-dotrhosts` module to inventory and delete `~/.rhosts` files. This ensures you are protected in the future, if somebody adds a `~/.rhosts` file.

## Inventory

With Mission Portal you can find hosts which have `~/.rhosts` files and details about reasons for exception:

[![Inventory Report showing found ~/.rhosts and Exception](https://raw.githubusercontent.com/cfengine/modules/master/security/delete-home-dotrhosts/media/inventory-report.png)](https://raw.githubusercontent.com/cfengine/modules/master/security/delete-home-dotrhosts/media/inventory-report.png)

## Example

If you try creating a `~/.rhosts` file running the agent with this module, you should see it get removed:

Example output with an exception present:

```
$ sudo touch /root/.rhosts /home/vagrant/.rhosts
# sudo cf-agent -KI
R: Found /home/vagrant/.rhosts, /root/.rhosts, but not removing because of exception: I got an exception for .rhosts from the security czar. See JIRA-1234 for more info.
```

Example output without exception present:

```
$ sudo cf-agent -KI
    info: Deleted file '/home/vagrant/.rhosts'
    info: Deleted file '/root/.rhosts'
```

## Configuration

### Specifying home directory roots to search

Define a [variable](https://docs.cfengine.com/docs/master/reference-language-concepts-variables.html) `delete_home_dotrhosts:main.home_dir_roots` as a string list with each element being a home directory root to search.
One easy way to define a variable is using [augments](https://docs.cfengine.com/docs/master/reference-language-concepts-augments.html#top) (another is using Host specific data, as seen below).

### Adding exceptions

If `~/.rhosts` files are really needed on some hosts, you can add an exception in one of two ways:

* Define the `exception_delete_home_rotshosts` class.
* Define the `delete_home_dotrhosts:main.exception` variable as a string with the reason for the exception as its value.

Functionally, they do the same, but the variable allows you to more richly communicate the reasons for exceptions in an **Inventory report** (as seen above).
This can be done from the **Host specific data** section in host info pages inside Mission Portal, the CFEngine Enterprise Web UI.
Here is an example of setting the variable:

[![Host specific data UI, setting the variable delete_home_dotrhosts:main.exception](https://raw.githubusercontent.com/cfengine/modules/master/security/delete-home-dotrhosts/media/host-specific-data.png)](https://raw.githubusercontent.com/cfengine/modules/master/security/delete-home-dotrhosts/media/host-specific-data.png)
