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
#       "nodejs" -> { "nodejs_app_server", "security_team" }
#         handle  => "main_nodejs_stream_20_installed",
#         comment => "Pin nodejs to stream 20 before packages: promises run",
#         meta    => { "service:nodeapp", "stream:20" },
#         state   => "installed",
#         stream  => "20";
#
#       "postgresql"
#         handle  => "main_postgresql_default",
#         state   => "default";
# }
#
# Setting a handle is strongly recommended: it appears in the DNF history
# Comment field alongside the bundle and policy file, giving auditors a
# direct pointer back to the exact promise that made the change.

import sys
import dnf
import dnf.exceptions
import re
from cfengine_module_library import PromiseModule, ValidationError, Result

# Import ModuleBase if available (not available in test environment)
try:
    import dnf.module.module_base
except (ImportError, ModuleNotFoundError):
    dnf.module = None  # type: ignore


class AppStreamsPromiseTypeModule(PromiseModule):
    def __init__(self, **kwargs):
        super(AppStreamsPromiseTypeModule, self).__init__(
            name="appstreams_promise_module", version="0.0.1", **kwargs
        )

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
            validator=lambda x: self._validate_identifier(
                x, "stream name", required=False
            ),
        )
        self.add_attribute(
            "profile",
            str,
            required=False,
            validator=lambda x: self._validate_identifier(
                x, "profile name", required=False
            ),
        )
        self.add_attribute(
            "options",
            list,
            required=False,
            default=[],
        )

        # Standard CFEngine promise attributes — passed through by the agent
        # and used to populate the DNF history comment for audit traceability.
        self.add_attribute("handle", str, required=False)
        self.add_attribute("comment", str, required=False)

    def _validate_state(self, value):
        accepted = ("enabled", "disabled", "installed", "removed", "default", "reset")
        if value not in accepted:
            accepted_str = "', '".join(accepted)
            raise ValidationError(f"State attribute must be '{accepted_str}'")

    def _validate_module_name(self, name):
        self._validate_identifier(name, "module name")

    def _validate_stream_name(self, stream):
        self._validate_identifier(stream, "stream name", required=False)

    def _validate_profile_name(self, profile):
        self._validate_identifier(profile, "profile name", required=False)

    def _validate_identifier(self, value, label, required=True):
        if not required and not value:
            return
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", value):
            raise ValidationError(
                f"Invalid {label}: {value!r}. Only alphanumeric, underscore, "
                f"dot, and dash characters are allowed."
            )

    def validate_promise(self, promiser, attributes, metadata):
        if not isinstance(promiser, str):
            raise ValidationError("Promiser must be of type string")
        self._validate_identifier(promiser, "module name")

    def evaluate_promise(self, promiser, attributes, metadata):
        module_name = promiser
        state = attributes.get("state", "enabled")
        stream = attributes.get("stream", None)
        profile = attributes.get("profile", None)
        options = attributes.get("options", [])

        # Build a descriptive argv so dnf history records a meaningful
        # "Command Line" entry instead of leaving it blank.
        _cmdline = [f"cfengine-appstreams {module_name!r} state={state!r}"]
        if stream:
            _cmdline.append(f"stream={stream!r}")
        if profile:
            _cmdline.append(f"profile={profile!r}")
        if options:
            _cmdline.append(f"options={options!r}")
        _orig_argv, sys.argv = sys.argv, _cmdline

        base = dnf.Base()
        try:
            # Read configuration first so comment is set before plugins read it
            base.conf.assumeyes = True
            handle = attributes.get("handle", "")
            cf_comment = attributes.get("comment", "")
            extra = []
            if handle:
                extra.append(f"handle: {handle}")
            if cf_comment:
                extra.append(f"comment: {cf_comment}")
            extra_part = " | " + ", ".join(extra) if extra else ""
            base.conf.comment = (
                f"CFEngine appstreams promise: {module_name} state={state}{extra_part}"
            )

            # Load DNF plugins so transactions are recorded like the CLI would.
            # configure_plugins() is intentionally omitted: it opens a history
            # entry unconditionally and base.close() would commit a spurious
            # empty record on KEPT runs. init + pre_configure is sufficient for
            # the transaction() hook to fire when do_transaction() is called.
            base.init_plugins()
            base.pre_configure_plugins()

            base.read_all_repos()

            # Force metadata expiry so DNF re-downloads repo metadata rather
            # than using stale cache entries that may point to RPM paths from
            # previously interrupted transactions that no longer exist on disk.
            if base.repos:
                for repo in base.repos.iter_enabled():
                    repo.metadata_expire = 0

            base.fill_sack(load_system_repo=True)

            if base.sack is None:
                self.log_error("DNF sack is not available")
                return Result.NOT_KEPT
            if not hasattr(base.sack, "_moduleContainer"):
                self.log_error("DNF sack has no module container")
                return Result.NOT_KEPT
            mpc = base.sack._moduleContainer

            # Resolve "default" stream/profile to concrete values
            if stream == "default":
                stream = mpc.getDefaultStream(module_name)
                if not stream:
                    self.log_error(f"No default stream found for module {module_name}")
                    return Result.NOT_KEPT
                self.log_verbose(f"Resolved 'default' stream to '{stream}'")

            if profile == "default":
                resolved_stream = stream or mpc.getDefaultStream(module_name)
                profiles = mpc.getDefaultProfiles(module_name, resolved_stream)
                profile = profiles[0] if profiles else None
                if not profile:
                    self.log_error(f"No default profile found for module {module_name}")
                    return Result.NOT_KEPT
                self.log_verbose(f"Resolved 'default' profile to '{profile}'")

            current_state = self._get_module_state(mpc, module_name)

            if state == "enabled":
                if current_state == "enabled":
                    already_correct = True
                    if stream:
                        try:
                            already_correct = (
                                mpc.getEnabledStream(module_name) == stream
                            )
                        except RuntimeError:
                            pass  # cannot verify stream, assume correct
                    if already_correct:
                        self.log_verbose(f"Module {module_name} is already enabled")
                        return Result.KEPT
                return self._enable_module(mpc, base, module_name, stream)

            elif state == "disabled":
                if current_state == "disabled":
                    self.log_verbose(f"Module {module_name} is already disabled")
                    return Result.KEPT
                return self._disable_module(mpc, base, module_name)

            elif state == "installed":
                # Check if we need to switch streams
                try:
                    enabled_stream = mpc.getEnabledStream(module_name)
                    if stream and enabled_stream and enabled_stream != stream:
                        # Stream switch needed
                        self.log_info(
                            f"Switching module {module_name} from stream "
                            f"{enabled_stream} to {stream}"
                        )
                        return self._switch_module(
                            mpc, base, module_name, stream, profile, options
                        )
                except RuntimeError:
                    # Module not enabled yet, proceed with normal install
                    pass

                if self._is_module_installed_with_packages(
                    mpc, base, module_name, stream, profile
                ):
                    self.log_verbose(
                        f"Module {module_name} (stream: {stream}, "
                        f"profile: {profile}) is already present"
                    )
                    return Result.KEPT
                return self._install_module(
                    mpc, base, module_name, stream, profile, options
                )

            elif state == "removed":
                if current_state in ("removed", "disabled"):
                    self.log_verbose(
                        f"Module {module_name} is already absent or disabled"
                    )
                    return Result.KEPT
                return self._remove_module(mpc, base, module_name, stream, profile)

            elif state in ("default", "reset"):
                return self._reset_module(mpc, base, module_name)

            self.log_error(f"Unexpected state '{state}' for module {module_name}")
            return Result.NOT_KEPT
        finally:
            base.close()
            sys.argv = _orig_argv

    def _get_module_state(self, mpc, module_name):
        state = mpc.getModuleState(module_name)
        if state == mpc.ModuleState_ENABLED:
            return "enabled"
        elif state == mpc.ModuleState_DISABLED:
            return "disabled"
        elif state == mpc.ModuleState_INSTALLED:
            return "installed"
        return "removed"

    def _is_module_installed_with_packages(
        self, mpc, base, module_name, stream, profile_name
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
            profiles = mpc.getDefaultProfiles(module_name, target_stream)
            profile_name = profiles[0] if profiles else None

        if profile_name:
            try:
                if profile_name not in mpc.getInstalledProfiles(module_name):
                    return False
            except RuntimeError:
                # RuntimeError is raised by libdnf if the module is unknown
                return False

            # Verify the profile's packages are actually installed as RPMs.
            # DNF's module database can mark a profile as installed even if the
            # RPM transaction failed (e.g. due to a stale cache error), leaving
            # the module state inconsistent with the actual system state.
            packages = self._get_profile_packages(
                mpc, module_name, target_stream, profile_name
            )
            if packages:
                installed_query = base.sack.query().installed()
                upgrade_query = base.sack.query().upgrades()
                for pkg in packages:
                    if not installed_query.filter(name=pkg):
                        self.log_verbose(
                            f"Profile '{profile_name}' is marked installed but "
                            f"package '{pkg}' is not present on the system"
                        )
                        return False
                    # If an upgrade is available the package is from an older
                    # stream — treat as not converged so _install_module runs
                    # and upgrades to the enabled stream's version.
                    if upgrade_query.filter(name=pkg):
                        self.log_verbose(
                            f"Package '{pkg}' has an available upgrade from "
                            f"stream '{target_stream}', needs repair"
                        )
                        return False

        return True

    def _enable_module(self, mpc, base, module_name, stream):
        """Enable a module stream without installing any packages."""
        target_stream = stream or mpc.getDefaultStream(module_name)
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
        """Disable a module stream so it cannot be enabled by dependency resolution."""
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
        # mpc.query(name) returns a vector of ModulePackage objects
        for module in mpc.query(module_name):
            if module.getStream() == stream:
                for profile in module.getProfiles():
                    if profile.getName() == profile_name:
                        return profile.getContent()
        return []

    def _log_failed_packages(self, failed_packages):
        for pkg, error in failed_packages:
            self.log_error(f"  Package {pkg} failed: {error}")

    def _apply_dnf_options(self, base, options):
        """Apply DNF configuration options, raising ConfigError on invalid options"""
        if not options:
            return

        for option in options:
            if "=" in option:
                key, value = option.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Raises dnf.exceptions.ConfigError if option is invalid
                base.conf.set_or_append_opt_value(key, value)
                self.log_verbose(f"Set DNF option: {key}={value}")

    def _switch_module(self, mpc, base, module_name, stream, profile, options=None):
        """Switch a module to a different stream using ModuleBase.switch_to()"""
        if options is None:
            options = []

        # Apply DNF configuration options
        try:
            self._apply_dnf_options(base, options)
        except dnf.exceptions.ConfigError as e:
            self.log_error(f"Invalid DNF option: {e}")
            return Result.NOT_KEPT

        if not stream:
            self.log_error("Stream must be specified for module switch")
            return Result.NOT_KEPT

        if not profile:
            profile = mpc.getDefaultProfiles(module_name, stream)
            profile = profile[0] if profile else None

        if not profile:
            self.log_error(
                f"No profile specified and no default found for {module_name}:{stream}"
            )
            return Result.NOT_KEPT

        # Use ModuleBase API to switch streams
        module_spec = f"{module_name}:{stream}/{profile}"
        self.log_verbose(f"Switching to module spec: {module_spec}")

        # Build command line for DNF history (shown in dnf history list)
        cmdline_parts = ["module", "switch-to", "-y", module_spec]
        if options:
            for opt in options:
                cmdline_parts.append(f"--setopt={opt}")
        base.args = cmdline_parts

        try:
            # Create ModuleBase wrapper around base
            module_base = dnf.module.module_base.ModuleBase(base)
            module_base.switch_to([module_spec])
        except dnf.exceptions.Error as e:
            self.log_error(f"Failed to switch module {module_spec}: {e}")
            return Result.NOT_KEPT

        # Resolve and execute transaction
        base.resolve()

        # Download packages before transaction (following DNF CLI pattern)
        pkgs_to_download = list(base.transaction.install_set)
        if pkgs_to_download:
            base.download_packages(pkgs_to_download)

        base.do_transaction()

        # Verify switch succeeded
        try:
            enabled_stream = mpc.getEnabledStream(module_name)
        except RuntimeError:
            self.log_error(
                f"Failed to get enabled stream for {module_name} after switch"
            )
            return Result.NOT_KEPT

        if enabled_stream != stream:
            self.log_error(
                f"Module {module_name} stream is {enabled_stream}, expected {stream}"
            )
            return Result.NOT_KEPT

        try:
            installed_profiles = mpc.getInstalledProfiles(module_name)
        except RuntimeError:
            self.log_error(
                f"Failed to get installed profiles for {module_name} after switch"
            )
            return Result.NOT_KEPT

        if profile not in installed_profiles:
            self.log_error(
                f"Profile {profile} not in installed profiles {installed_profiles}"
            )
            return Result.NOT_KEPT

        self.log_info(f"Module {module_name}:{stream}/{profile} switched successfully")
        return Result.REPAIRED

    def _install_module(self, mpc, base, module_name, stream, profile, options=None):
        """Enable a module stream and install the given (or default) profile's packages."""
        # Apply DNF options if specified
        try:
            self._apply_dnf_options(base, options)
        except dnf.exceptions.ConfigError as e:
            self.log_error(f"Invalid DNF option: {e}")
            return Result.NOT_KEPT

        if not stream:
            try:
                stream = mpc.getEnabledStream(module_name)
            except RuntimeError:
                pass
            stream = stream or mpc.getDefaultStream(module_name)

        if not profile:
            profiles = mpc.getDefaultProfiles(module_name, stream)
            profile = profiles[0] if profiles else None

        if not profile:
            self.log_error(
                f"No profile specified and no default found for {module_name}:{stream}"
            )
            return Result.NOT_KEPT

        # Use ModuleBase API for proper module context
        spec = f"{module_name}:{stream}/{profile}"

        # Build command line for DNF history (shown in dnf history list)
        cmdline_parts = ["module", "install", "-y", spec]
        if options:
            for opt in options:
                cmdline_parts.append(f"--setopt={opt}")
        base.args = cmdline_parts

        try:
            module_base = dnf.module.module_base.ModuleBase(base)
            module_base.install([spec])
        except dnf.exceptions.Error as e:
            self.log_error(f"Failed to install module {spec}: {e}")
            return Result.NOT_KEPT

        base.resolve()

        # Explicitly download packages before the transaction. Without this,
        # do_transaction() uses paths resolved during fill_sack(), which may
        # point to stale entries from a previously interrupted transaction that
        # no longer exist on disk, causing a FileNotFoundError.
        pkgs_to_download = list(base.transaction.install_set)
        if pkgs_to_download:
            base.download_packages(pkgs_to_download)

        base.do_transaction()

        # Verify using the module database only — not the RPM sack, which was
        # populated before the transaction and cannot see newly installed packages.
        try:
            profile_installed = profile in mpc.getInstalledProfiles(module_name)
        except RuntimeError:
            profile_installed = False

        if profile_installed:
            self.log_info(
                f"Module {module_name}:{stream}/{profile} installed successfully"
            )
            return Result.REPAIRED
        else:
            self.log_error(f"Failed to install module {module_name}:{stream}/{profile}")
            return Result.NOT_KEPT

    def _remove_module(self, mpc, base, module_name, stream, profile):
        """Uninstall profile packages and leave the stream in enabled (pinned) state."""
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
        profiles_to_remove = (
            [profile] if profile else mpc.getInstalledProfiles(module_name)
        )
        for p in profiles_to_remove:
            mpc.uninstall(module_name, target_stream, p)
            for pkg in self._get_profile_packages(mpc, module_name, target_stream, p):
                try:
                    base.remove(pkg)
                except dnf.exceptions.Error as e:
                    self.log_verbose(f"Failed to remove package {pkg}: {e}")
                    failed_packages.append((pkg, str(e)))

        mpc.save()
        base.resolve(allow_erasing=True)
        base.do_transaction()

        # Verify removal succeeded. After uninstalling a profile, DNF leaves
        # the stream in "enabled" state (stream pinned, no packages installed).
        # "removed" only occurs when the module is fully reset. Accept any
        # state other than "installed" as success.
        if self._get_module_state(mpc, module_name) != "installed":
            self.log_info(f"Module {module_name} removed successfully")
            return Result.REPAIRED
        else:
            self.log_error(f"Failed to remove module {module_name}")
            self._log_failed_packages(failed_packages)
            return Result.NOT_KEPT

    def _reset_module(self, mpc, base, module_name):
        """Reset a module to factory state — no stream pinned, no enabled/disabled flag."""
        if mpc.getModuleState(module_name) == mpc.ModuleState_DEFAULT:
            self.log_verbose(
                f"Module {module_name} is already in default (reset) state"
            )
            return Result.KEPT

        mpc.reset(module_name)
        mpc.save()
        base.resolve()
        base.do_transaction()

        # The in-memory mpc is not refreshed after do_transaction(), so
        # getModuleState() still reflects the pre-reset state. Trust the
        # operation — if no exception was raised the reset succeeded.
        self.log_info(f"Module {module_name} reset successfully")
        return Result.REPAIRED


if __name__ == "__main__":
    AppStreamsPromiseTypeModule().start()
