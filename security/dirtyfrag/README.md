Dirty Frag is a pair of kernel page-cache write vulnerabilities affecting Linux kernel modules that use nonlinear sk_buff (skb) fragments. An unprivileged local attacker with access to a network namespace can trigger out-of-bounds memory writes, potentially leading to privilege escalation.

- **CVE-2026-43284** (xfrm-ESP/IPComp): Affects `esp4.ko`, `esp6.ko`, `ipcomp.ko`, and `ipcomp6.ko` modules when unprivileged user namespaces are enabled. Patched in stable kernel trees as of May 2026.
- **CVE-2026-43500** (RxRPC): Affects `rxrpc.ko` module. Patches available for some distros as of May 2026; mitigation via module blacklisting where unpatched.

## Vulnerability conditions

- **CVE-2026-43284**: Requires `esp4`, `esp6`, `ipcomp`, or `ipcomp6` kernel modules present AND `/proc/sys/kernel/unprivileged_userns_clone` set to `1`
- **CVE-2026-43500**: Requires `rxrpc` kernel module present (no additional prerequisites)

## Inventory

After adding this module you can view Dirty Frag vulnerability status in Mission Portal Inventory Report:

[![Inventory showing Dirty Frag status](https://raw.githubusercontent.com/cfengine/modules/master/security/dirtyfrag/inventory-status.png)](https://raw.githubusercontent.com/cfengine/modules/master/security/dirtyfrag/inventory-status.png)

- **Dirty Frag CVE-2026-43284 (xfrm-ESP) status**:
  - `VULNERABLE (esp4, esp6 loaded)` -- vulnerable modules currently in memory (names vary by host)
  - `VULNERABLE (modules on disk, none loaded)` -- modules present but not loaded; latent risk
  - `PATCHED (kernel fix applied)` -- running kernel version includes the fix (auto-detected or admin-declared)
  - `MITIGATED (blacklist in place)` -- modprobe blacklist active for esp4/esp6/ipcomp/ipcomp6
  - `MITIGATED (userns disabled)` -- `user.max_user_namespaces=0` sysctl active, blocking the exploit path without unloading IPsec
  - `NOT AFFECTED` -- vulnerable modules not present on this host
- **Dirty Frag CVE-2026-43500 (RxRPC) status**:
  - `VULNERABLE (rxrpc loaded)` -- module currently in memory
  - `VULNERABLE (module on disk, not loaded)` -- module present but not loaded; latent risk
  - `PATCHED (kernel fix applied)` -- running kernel version includes the fix (auto-detected or admin-declared)
  - `MITIGATED (blacklist in place)` -- modprobe blacklist active
  - `NOT AFFECTED` -- rxrpc module not present on this host

## Mitigation

Each CVE has an independent toggle and separate conf file:

**CVE-2026-43284** (ESP/IPComp) -- `/etc/modprobe.d/dirtyfrag-esp.conf`:

```
# Dirty Frag CVE-2026-43284 mitigation: block xfrm-ESP and IPComp
install esp4 /bin/false
install esp6 /bin/false
install ipcomp /bin/false
install ipcomp6 /bin/false
```

**CVE-2026-43500** (RxRPC) -- `/etc/modprobe.d/dirtyfrag-rxrpc.conf`:

```
# Dirty Frag CVE-2026-43500 mitigation: block RxRPC
install rxrpc /bin/false
```

This prevents the vulnerable modules from loading. When mitigation is first applied, already-loaded modules are unloaded via `rmmod`.

**CVE-2026-43284 alternative** (user namespaces) -- `/etc/sysctl.d/dirtyfrag-userns.conf`:

```
# Dirty Frag CVE-2026-43284 mitigation: disable unprivileged user namespaces
# Blocks ESP/IPComp exploit without disabling IPsec.
# WARNING: May affect rootless containers and sandboxed applications.
user.max_user_namespaces = 0
```

This blocks the ESP/IPComp exploit path without blacklisting the modules, preserving IPsec functionality. Use this instead of `mitigate_esp` on hosts that require IPsec. Note: this does **not** mitigate CVE-2026-43500 (RxRPC) and may break rootless containers (Podman, Docker rootless), Flatpak, and browser sandboxes. Applied via `sysctl --system` on first write.

All mitigations are **disabled by default** -- the module only reports status unless the corresponding CMDB variable (`dirtyfrag:main.mitigate_esp`, `dirtyfrag:main.mitigate_rxrpc`, or `dirtyfrag:main.mitigate_userns`) is set to `"true"`. See the table below for the full set of toggles.

## Usage

Add the policy to your inputs:

```
inputs "security/dirtyfrag/dirtyfrag.cf"
```

To enable mitigation, set one or both variables in your site's `def.json` (Augments):

```json
{
  "variables": {
    "dirtyfrag:main.mitigate_esp":    { "value": "true" },
    "dirtyfrag:main.mitigate_rxrpc":  { "value": "true" },
    "dirtyfrag:main.mitigate_userns": { "value": "true" },
    "dirtyfrag:main.esp_patched":     { "value": "true" },
    "dirtyfrag:main.rxrpc_patched":   { "value": "true" }
  }
}
```

| Variable | What it does | Trade-off |
|----------|-------------|-----------|
| `mitigate_esp` | Blacklists esp4, esp6, ipcomp, ipcomp6 | Breaks IPsec |
| `mitigate_rxrpc` | Blacklists rxrpc | Breaks AFS/RxRPC |
| `mitigate_userns` | Sets `user.max_user_namespaces=0` | May break rootless containers/sandboxes |
| `esp_patched` | Declare CVE-2026-43284 as patched | Admin must verify kernel is actually patched |
| `rxrpc_patched` | Declare CVE-2026-43500 as patched | Admin must verify kernel is actually patched |

Typical combinations:
- **Most hosts**: `mitigate_esp` + `mitigate_rxrpc` (full protection)
- **IPsec hosts**: `mitigate_userns` + `mitigate_rxrpc` (preserves IPsec)
- **Container hosts needing IPsec**: `mitigate_rxrpc` only (partial, accept ESP risk until patched kernel)

Default behavior (variables unset) is status-only reporting.

## Detection details

The module checks for vulnerable modules in three ways:

1. **On-disk `.ko` files** under `/lib/modules/$(kernel_version)/`
2. **Compressed variants** (`.ko.zst`, `.ko.xz`) on distros that compress modules
3. **Currently loaded modules** via `/sys/module/` entries

For CVE-2026-43284, the module also checks whether unprivileged user namespaces are enabled (`/proc/sys/kernel/unprivileged_userns_clone`), since the exploit requires namespace access.

## Kernel patch detection

The module automatically detects whether the running kernel includes fixes for the Dirty Frag CVEs by comparing the kernel version (`uname -r`) against known-patched versions from distro security advisories. This data is maintained in `patched-kernels.json`, shipped alongside the policy.

Currently tracked distros:

| Distro | CVE-2026-43284 | CVE-2026-43500 |
|--------|---------------|---------------|
| RHEL/CentOS/Alma/Rocky 8 | 4.18.0-553.123.2 | 4.18.0-553.123.2 |
| RHEL/CentOS/Alma/Rocky 9 | 5.14.0-611.54.1 | 5.14.0-611.54.3 |
| RHEL/CentOS/Alma/Rocky 10 | 6.12.0-124.55.2 | 6.12.0-124.55.3 |
| Debian 11 (Bullseye) | 5.10.251-4 | 5.10.251-4 |
| Debian 12 (Bookworm) | 6.1.170-3 | 6.1.170-3 |
| Debian 13 (Trixie) | 6.12.86-1 | 6.12.86-1 |
| SLES 15 SP7 | 6.4.0-150700.53.45.1 | 6.4.0-150700.53.45.1 |

When a patched kernel is detected, the status reports `PATCHED (kernel fix applied)` instead of `VULNERABLE`. The module uses `sort -V` (version sort from coreutils) to compare kernel versions.

For distros not in the data file, or hosts running custom/backported kernels, set the admin override variables `esp_patched` and/or `rxrpc_patched` to `"true"` via augments.

To update the patched kernel data, edit `patched-kernels.json` and redeploy. The data file is intentionally separate from the policy so it can be updated independently.

## Adding exceptions

To exclude specific hosts from mitigation, use conditional augments to override them to a value other than `"true"`.

## Mission Portal — operator reference

The module is structured to give Mission Portal operators four things: inventory columns for at-a-glance state, a filterable mitigation-method enum, queryable classes for targeting, and CVE-linked promise stakeholders for audit traceability.

### Inventory columns

| Attribute name | Values | Filterable as |
|---|---|---|
| `Dirty Frag CVE-2026-43284 (xfrm-ESP) status` | `VULNERABLE (...)`, `PATCHED (kernel fix applied)`, `MITIGATED (blacklist in place)`, `MITIGATED (userns disabled)`, `NOT AFFECTED` | starts-with regex (`^VULNERABLE`, `^PATCHED`, `^MITIGATED`) |
| `Dirty Frag CVE-2026-43500 (RxRPC) status` | same shape, no userns option | same |
| `Dirty Frag CVE-2026-43284 mitigation method` | `kernel-patch`, `modprobe`, `userns`, `admin-override`, `none`, `not-applicable` | exact match |
| `Dirty Frag CVE-2026-43500 mitigation method` | `kernel-patch`, `modprobe`, `admin-override`, `none`, `not-applicable` | exact match |

The detailed status strings are for humans; the method enums are for dashboards and filters.

### Queryable classes (collected as `report`, not in default inventory columns)

| Class | Meaning | Use case |
|---|---|---|
| `dirtyfrag_vulnerable` | Any tracked CVE is unmitigated on this host | Targeting: "patch these now" |
| `dirtyfrag_esp_mitigated` | ESP mitigation path is active (any of blacklist / userns / patched) | Audit: confirm coverage |
| `dirtyfrag_rxrpc_mitigated` | RxRPC mitigation path is active | Same |
| `dirtyfrag_esp_needs_mitigation` | ESP exposure exists and no mitigation in place | Targeting fragments |
| `dirtyfrag_rxrpc_needs_mitigation` | Same for RxRPC | Same |
| `dirtyfrag_esp_present`, `dirtyfrag_rxrpc_present` | Module is loadable or loaded | Scoping |

Tagged with `meta => { "report" }` so cf-hub collects them for queries but they don't add columns to the default inventory view.

### Recommended alerts

Configure in Mission Portal → **Alerts**. The module ships no alerts itself; operators wire conditions appropriate to their fleet's risk tolerance:

- **Inventory condition** — alert when `Dirty Frag CVE-2026-43284 (xfrm-ESP) status` matches regex `^VULNERABLE`. Catches new unmitigated hosts as they join the fleet or as kernels regress.
- **Inventory condition** — alert when `Dirty Frag CVE-2026-43284 mitigation method` equals `userns` on more than N hosts. The userns path is fragile (breaks rootless containers); knowing how many hosts depend on it informs upgrade prioritization.
- **Policy condition** — alert on any **promises not kept** for handles `dirtyfrag_esp_modprobe_blacklist`, `dirtyfrag_rxrpc_modprobe_blacklist`, `dirtyfrag_esp_modprobe_unload`, `dirtyfrag_rxrpc_modprobe_unload`, `dirtyfrag_userns_sysctl_conf`, `dirtyfrag_userns_sysctl_reapply`. These are the file/command promises that enforce mitigation; a failure means the conf wasn't written or the module wasn't unloaded.

### Promise handles (for report filtering)

| Handle | What | When it fails |
|---|---|---|
| `dirtyfrag_esp_modprobe_blacklist` | Writes `/etc/modprobe.d/dirtyfrag-esp.conf` | Filesystem error, conflicting writes |
| `dirtyfrag_rxrpc_modprobe_blacklist` | Writes `/etc/modprobe.d/dirtyfrag-rxrpc.conf` | Same |
| `dirtyfrag_userns_sysctl_conf` | Writes `/etc/sysctl.d/dirtyfrag-userns.conf` | Same |
| `dirtyfrag_esp_modprobe_unload` | `modprobe -r` on currently-loaded ESP/IPComp modules | Module busy (existing IPsec tunnel) |
| `dirtyfrag_rxrpc_modprobe_unload` | `modprobe -r rxrpc` | Module busy |
| `dirtyfrag_userns_sysctl_reapply` | `sysctl --system` to load the userns conf | sysctl conf rejected |

### Compliance traceability

Every file and command promise carries a **promisee arrow** linking to its CVE: `"${path}" -> { "CVE-2026-43284" }` and `"${path}" -> { "CVE-2026-43500" }`. In Mission Portal's promise detail view, this surfaces as the stakeholder / linked identifier. Searching the audit history for `CVE-2026-43284` returns every policy artifact addressing it.

