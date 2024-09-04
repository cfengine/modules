# package-method-winget

## Usage
This module enables a `winget` package method used with policy like:

```cf3
packages:
  windows::
    "Microsoft.WindowsTerminal"
      package_method => winget,
      package_policy => "add";
```

## Opt-in for accepting source and package agreements (Required)

In order for winget to operate properly you must opt-in to accepting source and packaging agreements.
Without this acceptance the package method will fail with a message like:

```console
    info: Installing Microsoft.WindowsTerminal...
    info: Q:powershell.exe -Comm ...:You must set some vars for package-method-winget to work
   error: Finished command related to promiser 'Microsoft.WindowsTerminal' -- an error occurred, returned 1
   error: Bulk package schedule execution failed somewhere - unknown outcome for 'Microsoft.WindowsTerminal'
```

Acceptance can be given either via cfbs inputs, augments, group or host specific data.

Set the value of `yes` in the following variables:
- `data:package_method_winget.accept_source_agreements`
- `data:package_method_winget.accept_package_agreements`

## Installation
This module uses both the `winget` command as well as the `Microsoft.WinGet.Client` PowerShell module as that makes it easier to gather the list of currently installed packages.

`winget` should be installed on most newer desktop systems by default.
Server images often do not have `winget` installed.

In order for `winget` and `Microsoft.WinGet.Client` to be installed, ps1 scripts must be run which requires `PowerShell Execution policy` `Unrestricted` for `LocalMachine`.
The policy by default will not make this change.
You must opt-in by setting the variable `winget_installed.allow_powershell_execution_policy_change` to the value of `yes`.
This can be set in Host/Group data or via Augments in the `data` namespace.

```json
{
  "variables": {
    "data:winget_installed.allow_powershell_execution_policy_change": {
      "value": "yes"
    }
  }
}
```

