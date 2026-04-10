Inventory module for collecting SMART drive health, temperature, and wear data via smartctl.

## Description

This module collects S.M.A.R.T. (Self-Monitoring, Analysis and Reporting Technology) data from storage devices and exposes it as inventory attributes in CFEngine Mission Portal. It monitors drive health status, temperature, power-on hours, and NVMe-specific metrics.

SMART data helps predict drive failures before they occur and provides visibility into storage device health across your infrastructure.

## Requirements

- **Platform:** Linux only (currently)
- **Binary:** `smartctl` from smartmontools package (version 7.0+ for JSON support)
- **Permissions:** Requires root to read SMART data from devices

### Installation

Add to your policy via cfbs:

```bash
cfbs add inventory-smartctl
cfbs install
```

Or include directly in your policy:

```cfengine
bundle agent main
{
  methods:
      "smartctl" usebundle => inventory_smartctl:main;
}
```

## Inventory Attributes

The following attributes are exposed in Mission Portal:

### Universal Attributes (all drive types)

- **SMART drive health** - Per-drive health status
  - Values: `PASSED`, `FAILED`, `SMARTCTL_MISSING`
  - Example: `/dev/sda: PASSED`, `/dev/nvme0: FAILED`
  - `SMARTCTL_MISSING`: Indicates smartctl is not installed on the system
  - Critical: A FAILED status indicates the drive is predicting imminent failure

- **SMART drive model** - Drive model identifier
  - Example: `/dev/sda: Samsung SSD 870 EVO`

- **SMART drive temperatures (C)** - Current temperature in Celsius
  - Example: `/dev/sda: 35 C`
  - Note: Not available for virtual disks

- **SMART drive power-on hours** - Cumulative runtime in hours
  - Example: `/dev/sda: 8742 h`
  - Useful for tracking drive age and warranty coverage

### NVMe-Specific Attributes

- **SMART NVMe available spare** - Remaining spare blocks (%)
  - Example: `/dev/nvme0: 100%`
  - Low values (<10%) indicate wear approaching end of life

- **SMART NVMe percentage used** - Drive life consumed (%)
  - Example: `/dev/nvme0: 5%`
  - Based on manufacturer's endurance rating

- **SMART NVMe media errors** - Uncorrectable media errors count
  - Example: `/dev/nvme0: 0`
  - Any non-zero value indicates data integrity issues

### Alert Attributes

- **SMART failed drives** - List of drives with FAILED health status
  - Only present when one or more drives are failing
  - Use for alerting and automated response

## Troubleshooting

### SMARTCTL_MISSING appears in inventory

The module reports `SMARTCTL_MISSING` when smartctl is not installed. To resolve:

**Install smartmontools package:**

```sh
# Debian/Ubuntu
apt-get install smartmontools

# RHEL/CentOS/Fedora
yum install smartmontools

# SUSE
zypper install smartmontools
```

**Verify installation:**

```sh
command -v smartctl
smartctl --version
```

### No inventory data appears

If smartctl is installed but no data appears:

**Check if drives are detected:**

```sh
smartctl --scan
```

**Check cache files:**

```sh
ls -lh /var/cfengine/state/inventory_smartctl_*.json
```

**Run with verbose mode:**

```sh
cf-agent -Kvf ./policy.cf
```

## See Also

- [CFEngine inventory tutorial](https://docs.cfengine.com/docs/lts/examples/tutorials/custom_inventory/)
- [CFEngine Masterfiles inventory policy](https://docs.cfengine.com/docs/lts/reference/masterfiles-policy-framework/inventory/)
- [smartmontools documentation](https://www.smartmontools.org/)
