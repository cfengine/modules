A CFEngine custom promise type for managing AppStream modules on compatible systems.

## Overview

The `appstreams` promise type allows you to manage AppStream modules, which are a key feature of RHEL 8+ and compatible systems. AppStreams provide multiple versions of software components that can be enabled or disabled as needed.

## Features

- Enable, disable, install, and remove AppStream modules
- Support for specifying streams and profiles
- Automatic stream switching (upgrades and downgrades)
- Generic DNF configuration options support
- Audit trail support via handle and comment attributes

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

### Stream switching (upgrade or downgrade)

When a module is already installed with a different stream, the promise type automatically switches to the requested stream:

```
bundle agent main
{
  appstreams:
      "php"
        handle => "main_php_stream_82",
        comment => "Upgrade PHP from 8.1 to 8.2 for new features",
        state => "installed",
        stream => "8.2",
        profile => "minimal";
}
```

This will automatically switch from any currently installed stream (e.g., 8.1) to stream 8.2.

### Using DNF options

You can pass generic DNF configuration options to control package installation behavior:

```
bundle agent main
{
  appstreams:
      "php"
        state => "installed",
        stream => "8.2",
        profile => "minimal",
        options => {
          "install_weak_deps=false",
          "best=true"
        };
}
```

This installs PHP 8.2 minimal profile without weak dependencies (like httpd).

## Attributes

The promise type supports the following attributes:

- `state` (optional) - Desired state of the module: `enabled`, `disabled`, `installed`, `removed`, `default`, or `reset` (default: `enabled`)
- `stream` (optional) - Specific stream of the module to use. Set to `default` to use the module's default stream.
- `profile` (optional) - Specific profile of the module to install. Set to `default` to use the module stream's default profile.
- `options` (optional) - List of DNF configuration options as "key=value" strings (e.g., `{ "install_weak_deps=false", "best=true" }`). Invalid options will cause the promise to fail.
- `handle` (optional) - CFEngine handle for the promise, recorded in DNF history for audit traceability.
- `comment` (optional) - CFEngine comment for the promise, recorded in DNF history for audit traceability.

## Requirements

- CFEngine 3.18 or later
- Python 3
- DNF Python API (python3-dnf package)
- DNF/YUM package manager (RHEL 8+, Fedora, CentOS 8+)
- AppStream repositories configured
