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
#         state => "present",
#         stream => "12";
#
#       "postgresql"
#         state => "default";
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
        if value not in (
            "enabled", "disabled", "install", "remove", "default", "reset",
            "present", "absent"
        ):
            raise ValidationError(
                "State attribute must be 'enabled', 'disabled', 'install', "
                "'remove', 'default', 'reset', 'present', or 'absent'"
            )

    def _validate_module_name(self, name):
        # Validate module name to prevent injection
        if not re.match(r'^[a-zA-Z0-9_.-]+$', name):
            raise ValidationError(
                f"Invalid module name: {name}. Only alphanumeric, underscore, "
                f"dot, and dash characters are allowed."
            )

    def _validate_stream_name(self, stream):
        # Validate stream name to prevent injection
        if stream and not re.match(r'^[a-zA-Z0-9_.-]+$', stream):
            raise ValidationError(
                f"Invalid stream name: {stream}. Only alphanumeric, underscore, "
                f"dot, and dash characters are allowed."
            )

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

        # Handle stream => "default"
        if stream == "default":
            stream = self._get_default_stream(module_base, module_name)
            if not stream:
                self.log_error(
                    f"No default stream found for module {module_name}"
                )
                return Result.NOT_KEPT
            self.log_verbose(f"Resolved 'default' stream to '{stream}'")

        # Handle profile => "default"
        if profile == "default":
            # We need the stream to check for default profile
            # If stream is None, DNF might pick default stream, but safer to have it resolved
            resolved_stream = stream
            if not resolved_stream:
                 resolved_stream = self._get_default_stream(module_base, module_name)
            
            profile = self._get_default_profile(module_base, module_name, resolved_stream)
            if not profile:
                self.log_error(
                    f"No default profile found for module {module_name}"
                )
                return Result.NOT_KEPT
            self.log_verbose(f"Resolved 'default' profile to '{profile}'")

        # Re-construct the module specification with resolved values
        module_spec = module_name
        if stream:
            module_spec += ":" + stream
        if profile:
            module_spec += "/" + profile

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
        elif state == "install" or state == "present":
            if current_state in ["installed", "enabled"]:
                # For "present" state, if it's already installed or enabled,
                # we need to check if the specific profile is installed
                if self._is_module_installed_with_packages(
                    module_base, module_name, stream, profile
                ):
                    self.log_verbose(
                        f"Module {module_name} (stream: {stream}, "
                        f"profile: {profile}) is already present"
                    )
                    return Result.KEPT
                else:
                    return self._install_module(module_base, module_spec)
            else:
                # Module is not enabled, need to install
                # (which will enable and install packages)
                return self._install_module(module_base, module_spec)
        elif state == "remove" or state == "absent":
            if current_state == "removed" or current_state == "disabled":
                self.log_verbose(
                    f"Module {module_name} is already absent or disabled"
                )
                return Result.KEPT
            else:
                return self._remove_module(module_base, module_spec)
        elif state == "default" or state == "reset":
            return self._reset_module(
                module_base, module_name, stream, module_spec
            )

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

    def _get_default_stream(self, module_base, module_name):
        """Find the default stream for a module"""
        try:
            module_list, _ = module_base._get_modules(module_name)
            for module in module_list:
                # DNF API: module.is_default is usually a boolean
                if getattr(module, "is_default", False):
                    return module.stream
            return None
        except Exception as e:
            self.log_debug(f"Error finding default stream for {module_name}: {e}")
            return None

    def _get_default_profile(self, module_base, module_name, stream):
        """Find the default profile for a module stream"""
        try:
            module_list, _ = module_base._get_modules(module_name)
            for module in module_list:
                if stream and module.stream != stream:
                    continue
                
                # If finding for specific stream (or default stream found)
                for profile in module.profiles:
                    if getattr(profile, "is_default", False):
                        return profile.name
            return None
        except Exception as e:
            self.log_debug(f"Error finding default profile for {module_name}: {e}")
            return None

    def _is_module_installed_with_packages(
        self, module_base, module_name, stream, profile_name
    ):
        """Check if the module packages/profiles are installed on the system"""
        try:
            module_list, _ = module_base._get_modules(module_name)
            for module in module_list:
                if stream and module.stream != stream:
                    continue

                if module.status != "installed":
                    continue

                # If no profile is specified, 'installed' status is enough
                if not profile_name:
                    return True

                # If profile is specified, check if it's installed
                for profile in module.profiles:
                    if profile.name == profile_name:
                        return profile.status == "installed"

            return False
        except Exception as e:
            self.log_debug(
                f"Error checking if module packages are installed: {e}"
            )
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

    def _reset_module(self, module_base, module_name, stream, module_spec):
        """Reset a module using DNF Python API"""
        try:
            # First check if anything is enabled/installed for this module
            module_list, _ = module_base._get_modules(module_name)
            needs_reset = False
            for module in module_list:
                if stream and module.stream != stream:
                    continue
                if module.status in ("enabled", "disabled", "installed"):
                    needs_reset = True
                    break
            
            if not needs_reset:
                self.log_verbose(
                    f"Module {module_name} is already in default (reset) state"
                )
                return Result.KEPT

            module_base.reset([module_spec])
            module_base.base.resolve()
            module_base.base.do_transaction()
            self.log_info(f"Module {module_spec} reset successfully")
            return Result.REPAIRED
        except Exception as e:
            self.log_error(f"Failed to reset module {module_spec}: {str(e)}")
            return Result.NOT_KEPT


if __name__ == "__main__":
    DnfAppStreamPromiseTypeModule().start()