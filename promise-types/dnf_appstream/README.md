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

### Ensure a module is enabled

```
bundle agent main
{
  dnf_appstream:
      "nodejs"
        state => "enabled",
        stream => "12";
}
```

### Ensure a module is disabled

```
bundle agent main
{
  dnf_appstream:
      "nodejs"
        state => "disabled";
}
```

### Ensure a module is installed with a specific profile

```
bundle agent main
{
  dnf_appstream:
      "python36"
        state => "present",
        stream => "3.6",
        profile => "minimal";
}
```

### Ensure a module is absent

```
bundle agent main
{
  dnf_appstream:
      "postgresql"
        state => "absent";
}
```

### Reset a module to default

```
bundle agent main
{
  dnf_appstream:
      "nodejs"
        state => "default";
}
```

## Attributes

The promise type supports the following attributes:

- `state` (required) - Desired state of the module: `present`, `absent`, `enabled`, `disabled`, or `default` (default: `present`)
- `stream` (optional) - Specific stream of the module to use. Set to `"default"` to use the module's default stream.
- `profile` (optional) - Specific profile of the module to install. Set to `"default"` to use the module stream's default profile.

## Module States

- `present` - The module and its packages (profile) are present on the system (implies enabled). Alias: `install`.
- `absent` - The module is not present or is disabled. Alias: `remove`.
- `enabled` - The module is enabled and available for installation.
- `disabled` - The module is explicitly disabled.
- `default` - The module is in its default state (neither enabled nor disabled, no profiles installed). Alias: `reset`.

Note: The `present` state implies `enabled` because in DNF's module system, installing a module automatically enables it first.

## Requirements

- CFEngine 3.18 or later
- Python 3
- DNF Python API (python3-dnf package)
- DNF package manager (RHEL 8+, Fedora, CentOS 8+)
- AppStream repositories configured
