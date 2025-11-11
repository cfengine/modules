# AppStreams Promise Type

A CFEngine custom promise type for managing AppStream modules on compatible systems.

## Overview

The `appstreams` promise type allows you to manage AppStream modules, which are a key feature of RHEL 8+ and compatible systems. AppStreams provide multiple versions of software components that can be enabled or disabled as needed.

## Features

- Enable, disable, install, and remove AppStream modules
- Support for specifying streams and profiles

## Installation

To install this promise type, copy the `appstreams.py` file to your CFEngine masterfiles directory and configure the promise agent:

```
promise agent appstreams
{
  interpreter => "/usr/bin/python3";
  path => "$(sys.workdir)/modules/promises/appstreams.py";
}
```

## Usage

### Ensure a module is enabled

```
bundle agent main
{
  appstreams:
      "nodejs"
        state => "enabled",
        stream => "12";
}
```

### Ensure a module is disabled

```
bundle agent main
{
  appstreams:
      "nodejs"
        state => "disabled";
}
```

### Ensure a module is installed with a specific profile

```
bundle agent main
{
  appstreams:
      "python36"
        state => "installed",
        stream => "3.6",
        profile => "minimal";
}
```

### Ensure a module is removed

```
bundle agent main
{
  appstreams:
      "postgresql"
        state => "removed";
}
```

### Reset a module to default

```
bundle agent main
{
  appstreams:
      "nodejs"
        state => "default";
}
```

## Attributes

The promise type supports the following attributes:

- `state` (optional) - Desired state of the module: `enabled`, `disabled`, `installed`, `removed`, `default`, or `reset` (default: `enabled`)
- `stream` (optional) - Specific stream of the module to use. Set to `default` to use the module's default stream.
- `profile` (optional) - Specific profile of the module to install. Set to `default` to use the module stream's default profile.

## Requirements

- CFEngine 3.18 or later
- Python 3
- DNF Python API (python3-dnf package)
- DNF/YUM package manager (RHEL 8+, Fedora, CentOS 8+)
- AppStream repositories configured
