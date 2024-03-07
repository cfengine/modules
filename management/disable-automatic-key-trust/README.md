CFEngine provides a way to automatically trust keys from other hosts, which is enabled for all hosts on the same `/16` subnet as the hub by default.
Once your hosts are bootstrapped, or if you are using another way to establish trust (distribute keys) it is recommended to disable the automatic trust mechanism.
This module helps you do that, it is equivalent to editing the augments file (`/var/cfengine/masterfiles/def.json`) to:

```json
{
  "variables": {
    "default:def.trustkeysfrom": []
  }
}
```

After disabling automatic trust, take a look at:

- The [allow-hosts](https://build.cfengine.com/modules/allow-hosts/) module for specifying which hosts should be allowed to connect / fetch policy.
- The [secure bootstrap documentation](https://docs.cfengine.com/docs/3.21/getting-started-installation-secure-bootstrap.html) for more information on how to establish trust (distribute keys).

## Details

To connect / bootstrap a new client to a CFEngine hub, three things need to happen:

1. It must be **allowed to connect** over the network.
2. Its cryptographic **key must be trusted** by the hub.
3. It must be **allowed to access** the policy files it wants to download.

In CFEngine, these 3 things are controlled by the variables `def.control_server_allowconnects`, `def.trustkeysfrom` and `def.acl` (respectively).

By default, `def.acl` is set to the `/16` subnet of the hub's IP address.
If not overriden, the two other variables are set to default to the value as `def.acl`.

This means that, by default, any host which is on the same `/16` subnet as the hub is allowed to connect, automatically bootstrap and access the policy files.
This configuration is intented to make it easy to get started / test, but should be edited to a more secure configuration in a production environment.

By default, CFEngine only accepts incoming connections from IP addresses on the same network (`/16` subnet).
This module changes the setting to allow all IP addresses.

**Note:** The variables and defaults mentioned here are for the default CFEngine policy set (MPF).
If you are only using the CFEngine binaries, not the default policy, these variables don't do anything special.

For more information on this subject, see the [secure bootstrap section of our documentation](https://docs.cfengine.com/docs/3.21/getting-started-installation-secure-bootstrap.html).

## Examples

To better illustrate how this works, and what options are available, I've included some examples of what you could put in your `def.json` file below.

Allow connections from anywhere but don't trust any new keys:

```json
{
  "variables": {
    "default:def.acl": ["0.0.0.0/0", "::/0"],
    "default:def.control_server_allowconnects": ["0.0.0.0/0", "::/0"],
    "default:def.trustkeysfrom": []
  }
}
```

If you have set up just a couple of hosts, and want to only allow those, this is easy:

```json
{
  "variables": {
    "default:def.acl": ["1.2.3.4", "4.3.2.1"]
  }
}
```

(The IP addresses `1.2.3.4` and `4.3.2.1` are just examples here, replace them with the actual IP addresses of your hosts.)

Because of the defaults mentioned above, this is equivalent to:

```json
{
  "variables": {
    "default:def.acl": ["1.2.3.4", "4.3.2.1"],
    "default:def.control_server_allowconnects": ["1.2.3.4", "4.3.2.1"],
    "default:def.trustkeysfrom": ["1.2.3.4", "4.3.2.1"]
  }
}
```

Finally, if you want those only those 2 hosts to communicate, and only with those keys they already have, you can do this:

```json
{
  "variables": {
    "default:def.acl": ["1.2.3.4", "4.3.2.1"],
    "default:def.trustkeysfrom": []
  }
}
```
