The second field of `/etc/passwd` entries store the users password. An `x` in this field indicates that encrypted passwords are stored in `/etc/shadow`. An empty field indicates the user can log in without any password, `*` or `!` indicate that the account does not have a password and no password will access the account. Any value other than `x` is considered insecure as `/etc/shadow` is not used.

****Recommendation:**** `inventory-unshadowed-users` module to inventory offending entries.

## Inventory

- Local users not using hashed password :: List of usernames found not using hashed passwords.

With Mission Portal you can find hosts have users who are not using hashed passwords:

[![Inventory Report showing users who are not using shadowed passwords](https://raw.githubusercontent.com/cfengine/modules/master/security/inventory-unshadowed-users/media/inventory-report.png)](https://raw.githubusercontent.com/cfengine/modules/master/security/inventory-unshadowed-users/media/inventory-report.png)

## Example

If you have an entry in `/etc/password` where the second field is **not** `x`:

Example output with offending entries:

```
$ sudo bash -c 'cat << EOF >> /etc/passwd
emptyfield::9991:9991:testa:/home/emptyfield:/sbin/nologin
starfield:*:9992:9992:testb:/home/starfield:/sbin/nologin
EOF'
$ sudo cf-agent -K --show-evaluated-vars=inventory_unshadowed_users:main
Variable name                            Variable value                                               Meta tags                                Comment
inventory_unshadowed_users:main.inventory[emptyfield] emptyfield                                                   source=promise,inventory,attribute_name=Local users not using hashed password Inventory of local user who is not using a hashed password (lacks 'x' in second field of '/etc/passwd').
inventory_unshadowed_users:main.inventory[starfield] starfield                                                    source=promise,inventory,attribute_name=Local users not using hashed password Inventory of local user who is not using a hashed password (lacks 'x' in second field of '/etc/passwd').
```
