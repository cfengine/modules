Full disk encryption (FDE) protects data at rest by encrypting entire block devices.
This module detects mounted volumes backed by dm-crypt (LUKS1, LUKS2, or plain dm-crypt) on Linux systems and reports whether all, some, or none of the non-virtual block device filesystems are encrypted.

Detection is performed entirely through virtual filesystem reads (`/sys/block/` and `/proc/mounts`), with no dependency on external commands like `dmsetup` or `findmnt`.

## How it works

1. Enumerates device-mapper block devices from `/sys/block/dm-*`
2. Reads each device's DM subsystem UUID from `/sys/block/dm-N/dm/uuid`
3. Identifies crypt devices by the `CRYPT-` prefix in the UUID
4. Parses `/proc/mounts` to find all non-virtual block device mounts (excluding loop devices)
5. Classifies each mount as encrypted or unencrypted by checking if its device matches a crypt device path

## Inventory

- **Full disk encryption enabled** -- `yes` if all non-virtual block device filesystems are encrypted, `partial` if some are encrypted and some are not, `no` if none are encrypted.
- **Full disk encryption method** -- The encryption type(s) detected, e.g. `LUKS2`, `LUKS1`, `PLAIN`, or `none`. Multiple types are comma-separated if different methods are in use.
- **Full disk encryption volumes** -- List of mountpoints backed by encrypted devices.
- **Unencrypted volumes** -- List of mountpoints on non-virtual block devices that are not encrypted.

## Example

A system with LUKS2-encrypted root but unencrypted `/boot` and `/boot/efi`:

```
$ sudo cf-agent -Kf ./inventory-fde.cf --show-evaluated-vars=inventory_fde
Variable name                            Variable value                                               Meta tags                                Comment
inventory_fde:main.fde_enabled           partial                                                      source=promise,inventory,attribute_name=Full disk encryption enabled
inventory_fde:main.fde_method            LUKS2                                                        source=promise,inventory,attribute_name=Full disk encryption method
inventory_fde:main.fde_volumes            {"/"}                                                       source=promise,inventory,attribute_name=Full disk encryption volumes
inventory_fde:main.unencrypted_volumes    {"/boot","/boot/efi"}                                       source=promise,inventory,attribute_name=Unencrypted volumes
```

## Platform

- Linux only (requires `/sys/block/` and `/proc/mounts`)
