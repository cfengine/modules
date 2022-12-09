The `/etc/passwd` file contains information about local users on the system.
This file is readable by different users on the system to allow them to look up usernames and translate between UIDs and usernames.

Historically, this file contained passwords, in plaintext even, for early versions of UNIX.
Passwords should never be stored in plaintext, and this security issue was addressed by
by replacing them with encrypted / hashed passwords (different algorithms have been used).

Even then, since the `/etc/passwd` file is readable by other users, an attacker could see the hashes and perform an offline brute force attack.
To prevent this, a new file was introduced, `/etc/shadow`, containing users passwords.
This file could have more restrictive permissions, preventing users from seeing each others password hashes.
The passwords in the second column of the `/etc/passwd` file were replaced by `x`, indicating `/etc/passwd` is used.

Other possible values for the password field are: empty field (user can log in without a password), `*` or `!` (account does not have a password and no password will access the account).
Any value other than `x` is considered insecure as `/etc/shadow` is not used.

**Recommendation:** In the `/etc/passwd` file, only `x` should be allowed in the second column (password field).
This indicates that the `/etc/shadow` file is used.
Any other users ("unshadowed" users) should be forced to change password or deleted.
Use this `inventory-unshadowed-users` module to give you an overview of any problematic users in your infrastructure.

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

**Note:** We initially published this module and described it as ensuring users are not using unhashed passwords.
This was an oversight, as it's a long time since passwords were plaintext in `/etc/passwd`.
The main concern here is that the hash is in the wrong file, allowing other users to read it and perform an offline brute force attack on it.
We should have named and explained this better, so the module name and description above has been updated.
The security advice remains the same; only `x` should be allowed in the password field in `/etc/passwd`.
