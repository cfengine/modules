#!/usr/bin/python3
#
# Custom promise type to manage DNF AppStream modules
# Uses cfengine_module_library.py library.
#
# Use it in the policy like this:
# promise agent dnf_appstream
# {
#   interpreter => "/usr/bin/python3";
#   path => "$(sys.inputdir)/dnf_appstream.py";
# }
# bundle agent main
# {
#   dnf_appstream:
#       "nodejs"
#         state => "enabled",
#         stream => "12";
# }

import dnf
import re
from cfengine_module_library import PromiseModule, ValidationError, Result


class DnfAppStreamPromiseTypeModule(PromiseModule):
    def __init__(self, **kwargs):
        super(DnfAppStreamPromiseTypeModule, self).__init__(
            name="dnf_appstream_promise_module", version="0.0.1", **kwargs
        )

        # Define all expected attributes with their types and validation
        self.add_attribute("state", str, required=True, default="enabled",
                          validator=lambda x: self._validate_state(x))
        self.add_attribute("stream", str, required=False,
                          validator=lambda x: self._validate_stream_name(x))
        self.add_attribute("profile", str, required=False)

    def _validate_state(self, value):
        if value not in ("enabled", "disabled", "installed", "removed"):
            raise ValidationError("State attribute must be 'enabled', 'disabled', 'installed', or 'removed'")

    def _validate_module_name(self, name):
        # Validate module name to prevent injection
        if not re.match(r'^[a-zA-Z0-9_.-]+$', name):
            raise ValidationError(f"Invalid module name: {name}. Only alphanumeric, underscore, dot, and dash characters are allowed.")

    def _validate_stream_name(self, stream):
        # Validate stream name to prevent injection
        if stream and not re.match(r'^[a-zA-Z0-9_.-]+$', stream):
            raise ValidationError(f"Invalid stream name: {stream}. Only alphanumeric, underscore, dot, and dash characters are allowed.")

    def validate_promise(self, promiser, attributes, meta):
        # Validate promiser (module name)
        if not isinstance(promiser, str):
            raise ValidationError("Promiser must be of type string")

        self._validate_module_name(promiser)

    def evaluate_promise(self, promiser, attributes, meta):
        module_name = promiser
        state = attributes.get("state", "enabled")
        stream = attributes.get("stream", None)
        profile = attributes.get("profile", None)

        # Construct the module specification
        module_spec = module_name
        if stream:
            module_spec += ":" + stream
        if profile:
            module_spec += "/" + profile

        # Create a DNF base object
        base = dnf.Base()

        # Read configuration
        base.conf.assumeyes = True

        # Read repository information
        base.read_all_repos()

        # Fill the sack (package database)
        base.fill_sack(load_system_repo='auto')

        # Access the module base
        module_base = base.module_base
        if module_base is None:
            self.log_error("DNF modules are not available")
            return Result.NOT_KEPT

        # Check current state of the module
        current_state = self._get_module_state(module_base, module_name, stream)

        # Determine what action to take based on desired state
        if state == "enabled":
            if current_state == "enabled":
                self.log_verbose(f"Module {module_name} is already enabled")
                return Result.KEPT
            else:
                return self._enable_module(module_base, module_spec)
        elif state == "disabled":
            if current_state == "disabled":
                self.log_verbose(f"Module {module_name} is already disabled")
                return Result.KEPT
            else:
                return self._disable_module(module_base, module_spec)
        elif state == "installed":
            if current_state in ["installed", "enabled"]:
                # For "installed" state, if it's already installed or enabled,
                # we need to install packages from it
                # But if it's already installed with packages, we're done
                if self._is_module_installed_with_packages(base, module_name, stream):
                    self.log_verbose(f"Module {module_name} is already installed with packages")
                    return Result.KEPT
                else:
                    # Module is enabled but packages are not installed
                    return self._install_module(module_base, module_spec)
            else:
                # Module is not enabled, need to install (which will enable and install packages)
                return self._install_module(module_base, module_spec)
        elif state == "removed":
            if current_state == "removed" or current_state == "disabled":
                self.log_verbose(f"Module {module_name} is already removed or disabled")
                return Result.KEPT
            else:
                return self._remove_module(module_base, module_spec)

    def _get_module_state(self, module_base, module_name, stream):
        """Get the current state of a module using DNF Python API"""
        try:
            # List all modules to check the current state
            module_list, _ = module_base._get_modules(module_name)

            for module in module_list:
                # Check if this is the stream we're looking for (if specified)
                if stream and module.stream != stream:
                    continue

                # Check the module state
                if module.status in ("enabled", "disabled", "installed"):
                    return module.status

            # If we get here, module is not found or not in the specified stream
            return "removed"

        except Exception as e:
            self.log_error(f"Error getting module state for {module_name}: {str(e)}")
            return "unknown"

    def _is_module_installed_with_packages(self, base, module_name, stream):
        """Check if the module packages are actually installed on the system"""
        try:
            # Check if packages from the module are installed
            # This is a more complex check that requires examining installed packages
            # to see if they are from the specified module
            return False  # Simplified for now - would need more complex logic
        except Exception:
            return False

    def _enable_module(self, module_base, module_spec):
        """Enable a module using DNF Python API"""
        try:
            module_base.enable([module_spec])
            module_base.base.resolve()
            module_base.base.do_transaction()
            self.log_info(f"Module {module_spec} enabled successfully")
            return Result.REPAIRED
        except Exception as e:
            self.log_error(f"Failed to enable module {module_spec}: {str(e)}")
            return Result.NOT_KEPT

    def _disable_module(self, module_base, module_spec):
        """Disable a module using DNF Python API"""
        try:
            module_base.disable([module_spec])
            module_base.base.resolve()
            module_base.base.do_transaction()
            self.log_info(f"Module {module_spec} disabled successfully")
            return Result.REPAIRED
        except Exception as e:
            self.log_error(f"Failed to disable module {module_spec}: {str(e)}")
            return Result.NOT_KEPT

    def _install_module(self, module_base, module_spec):
        """Install a module (enable + install default packages) using DNF Python API"""
        try:
            # Enable and install the module
            module_base.install([module_spec])
            module_base.base.resolve()
            module_base.base.do_transaction()
            self.log_info(f"Module {module_spec} installed successfully")
            return Result.REPAIRED
        except Exception as e:
            self.log_error(f"Failed to install module {module_spec}: {str(e)}")
            return Result.NOT_KEPT

    def _remove_module(self, module_base, module_spec):
        """Remove a module using DNF Python API"""
        try:
            # Get list of packages from the module to remove
            module_base.remove([module_spec])
            module_base.base.resolve()
            module_base.base.do_transaction()
            self.log_info(f"Module {module_spec} removed successfully")
            return Result.REPAIRED
        except Exception as e:
            self.log_error(f"Failed to remove module {module_spec}: {str(e)}")
            return Result.NOT_KEPT


if __name__ == "__main__":
    DnfAppStreamPromiseTypeModule().start()