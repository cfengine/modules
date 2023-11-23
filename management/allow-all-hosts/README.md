By default, CFEngine only accepts incoming connections from IP addresses on the same network (`/16` subnet).
This module changes the setting to allow all IP addresses.

**Warning:** This module is intended to make testing / demonstrations easier.
It should **not** be used for production setups.

## Details

Internally, this changes the value of the `default:def.control_server_allowconnects` and `default:def.acl` variables.
The 2 variables have the same default values, but control slightly different things:

* `default:def.control_server_allowconnects` - Works similar to a firewall. Controls which IP addresses are allowed to connect to the `cf-serverd`.
* `default:def.acl` - Controls access to files on the server, i.e. which IP addresses are allowed to fetch files, most notably the policy set from `/var/cfengine/masterfiles` on the hub.

Advanced users might want to configure each of these variables individually, or even customize specific access for specific folders.

You can achieve the same by editing `/var/cfengine/masterfiles/def.json`:

```
{
  "variables": {
    "default:def.control_server_allowconnects": ["0.0.0.0/0", "::/0"],
    "default:def.acl": ["0.0.0.0/0", "::/0"]
  }
}
```

You can also edit these variables using the CMDB feature in Mission Portal.

**Tip:** You can omit the first variable, it defaults to the value of `default:def.acl`, when not specified.

**Note:** The variables and defaults mentioned here are for the default CFEngine policy set (MPF).
If you are only using the CFEngine binaries, not the default policy, these variables don't do anything special.
