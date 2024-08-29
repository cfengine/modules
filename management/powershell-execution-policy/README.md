# powershell-execution-policy

This module inventories and allows to set the state of the various `scopes` for PowerShell Execution Policy.

See the [Set-ExecutionPolicy](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/set-executionpolicy?view=powershell-7.4) documentation for details about scope and state values.

## Example

```cf3
  "set_localmachine_unrestricted" usebundle => default:powershell_execution_policy_set("LocalMachine", "Unrestricted");
```
