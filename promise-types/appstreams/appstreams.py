#!/usr/bin/python3
#
# Custom promise type to manage AppStream modules
# Uses cfengine_module_library.py library.
#
# Use it in the policy like this:
# promise agent appstreams
# {
#   interpreter => "/usr/bin/python3";
#   path => "$(sys.workdir)/modules/promises/appstreams.py";
# }
# bundle agent main
# {
#   appstreams:
#       "nodejs"
#         state => "installed",
#         stream => "12";
#
#       "postgresql"
#         state => "default";
# }

import dnf
import dnf.exceptions
import re
from cfengine_module_library import PromiseModule, ValidationError, Result


class AppStreamsPromiseTypeModule(PromiseModule):
    def __init__(self, **kwargs):
        super(AppStreamsPromiseTypeModule, self).__init__(
            name="appstreams_promise_module", version="0.0.1", **kwargs
        )

        # Define all expected attributes with their types and validation
        self.add_attribute(
            "state",
            str,
            required=False,
            default="enabled",
            validator=lambda x: self._validate_state(x),
        )
        self.add_attribute(
            "stream",
            str,
            required=False,
            validator=lambda x: self._validate_stream_name(x),
        )
        self.add_attribute(
            "profile",
            str,
            required=False,
            validator=lambda x: self._validate_profile_name(x),
        )

    def _validate_state(self, value):
        if value not in (
            "enabled",
            "disabled",
            "installed",
            "removed",
            "default",
            "reset",
        ):
            raise ValidationError(
                "State attribute must be 'enabled', 'disabled', 'installed', "
                "'removed', 'default', or 'reset'"
            )

    def _validate_module_name(self, name):
        # Validate module name to prevent injection
        if not re.match(r"^[a-zA-Z0-9_.-]+$", name):
            raise ValidationError(
                f"Invalid module name: {name}. Only alphanumeric, underscore, "
                f"dot, and dash characters are allowed."
            )

    def _validate_stream_name(self, stream):
        # Validate stream name to prevent injection
        if stream and not re.match(r"^[a-zA-Z0-9_.-]+$", stream):
            raise ValidationError(
                f"Invalid stream name: {stream}. Only alphanumeric, underscore, "
                f"dot, and dash characters are allowed."
            )

    def _validate_profile_name(self, profile):
        # Validate profile name to prevent injection
        if profile and not re.match(r"^[a-zA-Z0-9_.-]+$", profile):
            raise ValidationError(
                f"Invalid profile name: {profile}. Only alphanumeric, underscore, "
                f"dot, and dash characters are allowed."
            )

    def validate_promise(self, promiser, attributes, metadata):
        # Validate promiser (module name)
        if not isinstance(promiser, str):
            raise ValidationError("Promiser must be of type string")

        self._validate_module_name(promiser)

    def evaluate_promise(self, promiser, attributes, metadata):
        module_name = promiser
        state = attributes.get("state", "enabled")
        stream = attributes.get("stream", None)
        profile = attributes.get("profile", None)

        base = dnf.Base()
        try:
            # Read configuration
            base.conf.assumeyes = True

            # Read repository information
            base.read_all_repos()

            # Fill the sack (package database)
            base.fill_sack(load_system_repo=True)

            # Get ModulePackageContainer from sack
            if base.sack is None:
                self.log_error("DNF sack is not available")
                return Result.NOT_KEPT
            if hasattr(base.sack, "_moduleContainer"):
                mpc = base.sack._moduleContainer
            else:
                self.log_error("DNF sack has no module container")
                return Result.NOT_KEPT

            # Handle stream => "default"
            if stream == "default":
                stream = self._get_default_stream(mpc, module_name)
                if not stream:
                    self.log_error(f"No default stream found for module {module_name}")
                    return Result.NOT_KEPT
                self.log_verbose(f"Resolved 'default' stream to '{stream}'")

            # Handle profile => "default"
            if profile == "default":
                # We need the stream to check for default profile
                # If stream is None, DNF might pick default stream, but safer to have it resolved
                resolved_stream = stream
                if not resolved_stream:
                    resolved_stream = self._get_default_stream(mpc, module_name)

                profile = self._get_default_profile(mpc, module_name, resolved_stream)
                if not profile:
                    self.log_error(f"No default profile found for module {module_name}")
                    return Result.NOT_KEPT
                self.log_verbose(f"Resolved 'default' profile to '{profile}'")

            # Check current state of the module
            current_state = self._get_module_state(mpc, module_name)

            # Determine what action to take based on desired state
            if state == "enabled":
                if current_state == "enabled":
                    # Check stream match
                    is_stream_correct = True
                    if stream:
                        try:
                            enabled_stream = mpc.getEnabledStream(module_name)
                            if enabled_stream != stream:
                                is_stream_correct = False
                        # RuntimeError is raised by libdnf if the module is unknown
                        except RuntimeError:
                            pass

                    if is_stream_correct:
                        self.log_verbose(f"Module {module_name} is already enabled")
                        return Result.KEPT
                    else:
                        return self._enable_module(mpc, base, module_name, stream)
                else:
                    return self._enable_module(mpc, base, module_name, stream)
            elif state == "disabled":
                if current_state == "disabled":
                    self.log_verbose(f"Module {module_name} is already disabled")
                    return Result.KEPT
                else:
                    return self._disable_module(mpc, base, module_name)
            elif state == "installed":
                if current_state in ["installed", "enabled"]:
                    # For "installed" state, if it's already installed or enabled,
                    # we need to check if the specific profile is installed
                    if self._is_module_installed_with_packages(
                        mpc, module_name, stream, profile
                    ):
                        self.log_verbose(
                            f"Module {module_name} (stream: {stream}, "
                            f"profile: {profile}) is already present"
                        )
                        return Result.KEPT
                    else:
                        return self._install_module(
                            mpc, base, module_name, stream, profile
                        )
                else:
                    # Module is not enabled, need to install
                    # (which will enable and install packages)
                    return self._install_module(mpc, base, module_name, stream, profile)
            elif state == "removed":
                if current_state == "removed" or current_state == "disabled":
                    self.log_verbose(
                        f"Module {module_name} is already absent or disabled"
                    )
                    return Result.KEPT
                else:
                    return self._remove_module(mpc, base, module_name, stream, profile)
            elif state == "default" or state == "reset":
                return self._reset_module(mpc, base, module_name)

            self.log_error(f"Unexpected state '{state}' for module {module_name}")
            return Result.NOT_KEPT
        finally:
            base.close()

    def _get_module_state(self, mpc, module_name):
        """Get the current state of a module using DNF Python API"""
        state = mpc.getModuleState(module_name)
        if state == mpc.ModuleState_ENABLED:
            return "enabled"
        elif state == mpc.ModuleState_DISABLED:
            return "disabled"
        elif state == mpc.ModuleState_INSTALLED:
            return "installed"
        return "removed"

    def _get_default_stream(self, mpc, module_name):
        """Find the default stream for a module"""
        return mpc.getDefaultStream(module_name)

    def _get_default_profile(self, mpc, module_name, stream):
        """Find the default profile for a module stream"""
        profiles = mpc.getDefaultProfiles(module_name, stream)
        if profiles:
            return profiles[0]
        return None

    def _is_module_installed_with_packages(
        self, mpc, module_name, stream, profile_name
    ):
        """Check if the module packages/profiles are installed on the system"""
        # Check stream
        try:
            enabled_stream = mpc.getEnabledStream(module_name)
        except RuntimeError:
            # RuntimeError is raised by libdnf if the module is unknown
            return False

        if stream and enabled_stream != stream:
            return False

        target_stream = stream or enabled_stream
        if not target_stream:
            return False

        # Check profile
        if not profile_name:
            profile_name = self._get_default_profile(mpc, module_name, target_stream)

        if profile_name:
            try:
                installed_profiles = mpc.getInstalledProfiles(module_name)
                return profile_name in installed_profiles
            except RuntimeError:
                # RuntimeError is raised by libdnf if the module is unknown
                return False

        return True

    def _enable_module(self, mpc, base, module_name, stream):
        """Enable a module using DNF Python API"""
        target_stream = stream or self._get_default_stream(mpc, module_name)

        if not target_stream:
            self.log_error(
                f"No stream specified and no default stream found for {module_name}"
            )
            return Result.NOT_KEPT

        mpc.enable(module_name, target_stream)
        mpc.save()
        mpc.moduleDefaultsResolve()
        base.resolve()
        base.do_transaction()
        if mpc.isEnabled(module_name, target_stream):
            self.log_info(f"Module {module_name}:{target_stream} enabled successfully")
            return Result.REPAIRED
        else:
            self.log_error(f"Failed to enable module {module_name}:{target_stream}")
            return Result.NOT_KEPT

    def _disable_module(self, mpc, base, module_name):
        """Disable a module using DNF Python API"""
        mpc.disable(module_name)
        mpc.save()
        base.resolve()
        base.do_transaction()
        if mpc.isDisabled(module_name):
            self.log_info(f"Module {module_name} disabled successfully")
            return Result.REPAIRED
        else:
            self.log_error(f"Failed to disable module {module_name}")
            return Result.NOT_KEPT

    def _get_profile_packages(self, mpc, module_name, stream, profile_name):
        # Find the module package
        # mpc.query(name) returns vector
        modules = mpc.query(module_name)
        for module in modules:
            if module.getStream() == stream:
                # Found stream
                for profile in module.getProfiles():
                    if profile.getName() == profile_name:
                        return profile.getContent()
        return []

    def _install_module(self, mpc, base, module_name, stream, profile):
        """Install a module using DNF Python API"""
        if not stream:
            try:
                stream = mpc.getEnabledStream(module_name)
            except RuntimeError:
                pass
            if not stream:
                stream = self._get_default_stream(mpc, module_name)

        if not profile:
            profile = self._get_default_profile(mpc, module_name, stream)

        if not profile:
            self.log_error(
                f"No profile specified and no default found for {module_name}:{stream}"
            )
            return Result.NOT_KEPT

        mpc.enable(module_name, stream)
        mpc.install(module_name, stream, profile)
        mpc.save()
        mpc.moduleDefaultsResolve()

        # Install packages
        packages = self._get_profile_packages(mpc, module_name, stream, profile)
        failed_packages = []
        if packages:
            for pkg in packages:
                try:
                    base.install(pkg)
                except dnf.exceptions.Error as e:
                    self.log_verbose(f"Failed to install package {pkg}: {e}")
                    failed_packages.append((pkg, str(e)))

        base.resolve()
        base.do_transaction()

        # Verify installation succeeded
        if self._is_module_installed_with_packages(mpc, module_name, stream, profile):
            self.log_info(
                f"Module {module_name}:{stream}/{profile} installed successfully"
            )
            return Result.REPAIRED
        else:
            self.log_error(f"Failed to install module {module_name}:{stream}/{profile}")
            if failed_packages:
                for pkg, error in failed_packages:
                    self.log_error(f"  Package {pkg} failed: {error}")
            return Result.NOT_KEPT

    def _remove_module(self, mpc, base, module_name, stream, profile):
        """Remove a module using DNF Python API"""
        if not stream:
            try:
                target_stream = mpc.getEnabledStream(module_name)
            except RuntimeError:
                target_stream = None
        else:
            target_stream = stream

        if not target_stream:
            self.log_verbose(f"No active stream for {module_name}, nothing to remove")
            return Result.KEPT

        failed_packages = []
        if profile:
            mpc.uninstall(module_name, target_stream, profile)
            pkgs = self._get_profile_packages(mpc, module_name, target_stream, profile)
            for pkg in pkgs:
                try:
                    base.remove(pkg)
                except dnf.exceptions.Error as e:
                    self.log_verbose(f"Failed to remove package {pkg}: {e}")
                    failed_packages.append((pkg, str(e)))
        else:
            profiles = mpc.getInstalledProfiles(module_name)
            for p in profiles:
                mpc.uninstall(module_name, target_stream, p)
                pkgs = self._get_profile_packages(mpc, module_name, target_stream, p)
                for pkg in pkgs:
                    try:
                        base.remove(pkg)
                    except dnf.exceptions.Error as e:
                        self.log_verbose(f"Failed to remove package {pkg}: {e}")
                        failed_packages.append((pkg, str(e)))

        mpc.save()
        base.resolve(allow_erasing=True)
        base.do_transaction()

        # Verify removal succeeded
        current_state = self._get_module_state(mpc, module_name)
        if current_state in ["removed", "disabled"]:
            self.log_info(f"Module {module_name} removed successfully")
            return Result.REPAIRED
        else:
            self.log_error(f"Failed to remove module {module_name}")
            if failed_packages:
                for pkg, error in failed_packages:
                    self.log_error(f"  Package {pkg} failed: {error}")
            return Result.NOT_KEPT

    def _reset_module(self, mpc, base, module_name):
        """Reset a module using DNF Python API"""
        if mpc.getModuleState(module_name) == mpc.ModuleState_DEFAULT:
            self.log_verbose(
                f"Module {module_name} is already in default (reset) state"
            )
            return Result.KEPT

        mpc.reset(module_name)
        mpc.save()
        base.resolve()
        base.do_transaction()

        # Verify reset succeeded
        if mpc.getModuleState(module_name) == mpc.ModuleState_DEFAULT:
            self.log_info(f"Module {module_name} reset successfully")
            return Result.REPAIRED
        else:
            self.log_error(f"Failed to reset module {module_name}")
            return Result.NOT_KEPT


if __name__ == "__main__":
    AppStreamsPromiseTypeModule().start()
