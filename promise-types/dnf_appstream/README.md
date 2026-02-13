# DNF AppStream Promise Type

A CFEngine custom promise type for managing DNF AppStream modules on compatible systems.

## Overview

The `dnf_appstream` promise type allows you to manage DNF AppStream modules, which are a key feature of RHEL 8+ and compatible systems. AppStreams provide multiple versions of software components that can be enabled or disabled as needed.

## Features

- Enable, disable, install, and remove DNF AppStream modules
- Support for specifying streams and profiles

## Installation

To install this promise type, copy the `dnf_appstream.py` file to your CFEngine masterfiles directory and configure the promise agent:

```
promise agent dnf_appstream
{
  interpreter => "/usr/bin/python3";
  path => "$(sys.workdir)/modules/promises/dnf_appstream.py";
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
        state => "installed",
        stream => "3.6",
        profile => "minimal";
}
```

### Ensure a module is removed

```
bundle agent main
{
  dnf_appstream:
      "postgresql"
        state => "removed";
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

- `state` (optional) - Desired state of the module: `enabled`, `disabled`, `installed`, `removed`, `default`, or `reset` (default: `enabled`)
- `stream` (optional) - Specific stream of the module to use. Set to `default` to use the module's default stream.
- `profile` (optional) - Specific profile of the module to install. Set to `default` to use the module stream's default profile.

## Requirements

- CFEngine 3.18 or later
- Python 3
- DNF Python API (python3-dnf package)
- DNF package manager (RHEL 8+, Fedora, CentOS 8+)
- AppStream repositories configured
