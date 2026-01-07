# DNF AppStream Promise Type

A CFEngine custom promise type for managing DNF AppStream modules on RHEL 8+ and compatible systems.

## Overview

The `dnf_appstream` promise type allows you to manage DNF AppStream modules, which are a key feature of RHEL 8+ and compatible systems. AppStreams provide multiple versions of software components that can be enabled or disabled as needed.

## Features

- Enable, disable, install, and remove DNF AppStream modules
- Support for specifying streams and profiles
- Input validation and sanitization for security
- Proper error handling and logging
- Module state checking to avoid unnecessary operations
- Uses DNF Python API for efficient and secure operations

## Installation

To install this promise type, copy the `dnf_appstream.py` file to your CFEngine masterfiles directory and configure the promise agent:

```
promise agent dnf_appstream
{
  interpreter => "/usr/bin/python3";
  path => "$(sys.inputdir)/dnf_appstream.py";
}
```

## Usage

### Enable a Module

```
bundle agent main
{
  dnf_appstream:
      "nodejs"
        state => "enabled",
        stream => "12";
}
```

### Disable a Module

```
bundle agent main
{
  dnf_appstream:
      "nodejs"
        state => "disabled";
}
```

### Install a Module with Profile

```
bundle agent main
{
  dnf_appstream:
      "python36"
        state => "installed",
        stream => "3.6",
        profile => "minimal";
}
```

### Remove a Module

```
bundle agent main
{
  dnf_appstream:
      "postgresql"
        state => "removed";
}
```

## Attributes

The promise type supports the following attributes:

- `state` (required) - Desired state of the module: `enabled`, `disabled`, `installed`, or `removed` (default: `enabled`)
- `stream` (optional) - Specific stream of the module to use
- `profile` (optional) - Specific profile of the module to install

## Module States

- `enabled` - The module is enabled and available for installation
- `disabled` - The module is disabled and not available for installation
- `installed` - The module is installed with its default profile (implies enabled)
- `removed` - The module is removed or not installed

Note: The `installed` state implies `enabled` because in DNF's module system, installing a module automatically enables it first.

## Security Features

- Input validation and sanitization
- Module name validation (alphanumeric, underscore, dot, and dash only)
- Stream name validation (alphanumeric, underscore, dot, and dash only)
- Uses DNF Python API for secure operations instead of subprocess calls
- Proper error handling and timeout management

## Requirements

- CFEngine 3.18 or later
- Python 3
- DNF Python API (python3-dnf package)
- DNF package manager (RHEL 8+, Fedora, CentOS 8+)
- AppStream repositories configured

## Examples

### Enable Multiple Modules

```
bundle agent enable_development_stack
{
  dnf_appstream:
      "nodejs"
        state => "enabled",
        stream => "14";

      "python36"
        state => "enabled",
        stream => "3.6";

      "postgresql"
        state => "enabled",
        stream => "12";
}
```

### Configure Web Server Stack

```
bundle agent configure_web_server
{
  dnf_appstream:
      "nginx"
        state => "installed",
        stream => "1.14";

      "php"
        state => "installed",
        stream => "7.4",
        profile => "minimal";
}
```

### Complete Example with Package Installation

```
promise agent dnf_appstream
{
    interpreter => "/usr/bin/python3";
    path => "$(sys.inputdir)/modules/promises/dnf_appstream.py";
}

body package_method dnf
{
    package_module => "dnf";
    package_policy => "present";
}

bundle agent setup_web_server
{
    # Enable AppStream modules
    dnf_appstream:
        "nodejs"
            state => "enabled",
            stream => "14";

        "postgresql"
            state => "installed",
            stream => "12";

    # Install packages from the enabled modules
    packages:
        # These packages will be installed from the enabled AppStream modules
        "nodejs" package_method => dnf;
        "postgresql-server" package_method => dnf;
        
        # Standard packages
        "nginx" package_method => dnf;
}
```