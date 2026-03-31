import os
import re
import subprocess
import tempfile

from cfengine_module_library import PromiseModule, ValidationError, Result


BASE_CONFIG = "/etc/ssh/sshd_config"
DROP_IN_DIR = "/etc/ssh/sshd_config.d/"
CFE_CONFIG = os.path.join(DROP_IN_DIR, "00-cfengine.conf")


# TODO: Add a "restart" attribute (default: True) to allow overriding the
#       automatic restart of sshd after configuration changes.
# TODO: Add a "start" attribute (default: False) to optionally start the sshd
#       service if it is not already running.
# TODO: Append the policy comment (e.g. "# Promised by CFEngine") as a trailing
#       comment on each directive written to the drop-in file.

REQUIRED_ATTRIBUTES = ("value",)  # Add required attributes here
ACCEPTED_ATTRIBUTES = REQUIRED_ATTRIBUTES + ()  # Add optional attributes here


def sshd_quote(value: str) -> str:
    """Quote a string for sshd_config. Values containing whitespace, '#', or
    '\"' are wrapped in double quotes, with internal backslashes and double
    quotes escaped."""
    if not value:
        return '""'
    if re.search(r'[\s#"]', value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def to_sshd_value(value) -> str:
    """Convert a Python value to an sshd config value. Lists are space-joined,
    individual strings are quoted when necessary."""
    if isinstance(value, list):
        return " ".join(sshd_quote(v) for v in value)
    if isinstance(value, str):
        return sshd_quote(value)
    raise TypeError(f"Expected str or list[str], got {type(value).__name__}")


def try_unlink(path: str):
    """Remove a file, ignoring errors if it no longer exists."""
    try:
        os.unlink(path)
    except OSError:
        pass


def is_drop_in_directive(directive: str) -> bool:
    """Check if a directive is an Include for the drop-in config directory."""
    m = re.match(
        rf"include(\s+|\s*=\s*){re.escape(DROP_IN_DIR)}\*\.conf",
        directive.strip(),
        re.IGNORECASE,
    )
    return m is not None


def update_result(old: str, new: str) -> str:
    """Return the worst of two results. Severity: KEPT < REPAIRED < NOT_KEPT."""
    if old == Result.NOT_KEPT or new == Result.NOT_KEPT:
        return Result.NOT_KEPT
    if old == Result.REPAIRED or new == Result.REPAIRED:
        return Result.REPAIRED
    return Result.KEPT


def get_first_directive(lines: list[str]) -> str | None:
    """Return the first non-comment, non-empty directive, or None if not found."""
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return None


class SshdPromiseTypeModule(PromiseModule):
    def __init__(self):
        super().__init__("sshd_promise_module", "0.0.0")

    def validate_promise(
        self, promiser: str, attributes: dict[str, object], metadata: dict[str, str]
    ):
        # Check that promiser is a valid sshd keyword
        if not re.fullmatch(r"[a-zA-Z0-9]+", promiser):
            raise ValidationError(
                f"Promiser '{promiser}' must be a valid sshd keyword containing only letters and numbers"
            )

        # Check for unknown attributes
        for attr in attributes:
            if attr not in ACCEPTED_ATTRIBUTES:
                raise ValidationError(f"Attribute '{attr}' is NOT accepted")

        # Check for any missing required attributes
        for attr in REQUIRED_ATTRIBUTES:
            if attr not in attributes:
                raise ValidationError(f"Missing required attribute '{attr}'")

        # Check type of 'value' attributes
        value = attributes.get("value")
        if not isinstance(value, (str, list)):
            raise ValidationError("Attribute 'value' must be a string or an slist")

        # Make sure 'value' attribute is not empty
        if not value:
            raise ValidationError("Attribute 'value' cannot be empty")

    def validate_config(self, filename: str) -> bool:
        """Validate the sshd syntax on a file"""
        r = subprocess.run(
            ["/usr/sbin/sshd", "-t", "-f", filename],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            self.log_error(f"Configuration validation failed: {r.stderr.strip()}")
            return False
        return True

    def safe_write_config(self, path: str, lines: list[str]) -> bool:
        """Atomically write config lines to a temporary file and replace the
        target only if sshd validates the syntax successfully."""
        directory = os.path.dirname(path)
        base = os.path.basename(path)
        prefix, suffix = os.path.splitext(base)

        fd, tmp_path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
        try:
            os.fchmod(fd, 0o600)  # rw-------
            with os.fdopen(fd, "w") as f:
                f.writelines(lines)
                f.flush()  # Push data to kernel buffer so sshd can read it
                success = self.validate_config(tmp_path)
                if success:
                    os.replace(tmp_path, path)
                return success
        finally:
            try_unlink(tmp_path)

    def ensure_include_directive(self) -> str:
        """Ensure the base sshd config includes the drop-in directory."""
        try:
            with open(BASE_CONFIG, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            self.log_error(f"Base configuration file '{BASE_CONFIG}' does not exist")
            return Result.NOT_KEPT

        first_directive = get_first_directive(lines)

        if (first_directive is None) or (not is_drop_in_directive(first_directive)):
            include_directive = f"Include {DROP_IN_DIR}*.conf"
            self.log_debug(
                f"Expected first directive in '{BASE_CONFIG}' to be '{include_directive}'"
            )

            lines.insert(0, f"{include_directive} # Added by CFEngine\n")
            try:
                if not self.safe_write_config(BASE_CONFIG, lines):
                    # Error already logged
                    return Result.NOT_KEPT
            except Exception as e:
                self.log_error(f"Failed to write '{BASE_CONFIG}': {e}")
                return Result.NOT_KEPT

            self.log_info(f"Added include directive to '{BASE_CONFIG}'")
            return Result.REPAIRED

        return Result.KEPT

    def ensure_drop_in_dir(self) -> str:
        """Ensure the drop-in config directory exists."""
        if os.path.isdir(DROP_IN_DIR):
            return Result.KEPT

        try:
            os.makedirs(DROP_IN_DIR, mode=0o755)  # rwxr-xr-x
        except Exception as e:
            self.log_error(f"Failed to create drop-in directory '{DROP_IN_DIR}': {e}")
            return Result.NOT_KEPT

        self.log_info(f"Created drop-in directory '{DROP_IN_DIR}'")
        return Result.REPAIRED

    def ensure_drop_in_config(self, keyword: str, value: str | list[str]) -> str:
        """Write the CFEngine drop-in config file with the given attribute"""

        try:
            with open(CFE_CONFIG, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            lines = []

        # Remove conflicting directives
        lines = [line for line in lines if not line.lower().startswith(keyword.lower())]

        # Remove the disclaimer so that we can put it back on top
        lines = [line for line in lines if not line.startswith("# ")]

        # Add the promised directive to the top (just after the disclaimer)
        disclaimer = ["# Managed by CFEngine\n", "# Do NOT manually edit this file\n"]
        lines = disclaimer + [f"{keyword} {to_sshd_value(value)}\n"] + lines

        try:
            if not self.safe_write_config(CFE_CONFIG, lines):
                return Result.NOT_KEPT
        except Exception as e:
            self.log_error(f"Failed to write drop-in config '{CFE_CONFIG}': {e}")
            return Result.NOT_KEPT

        self.log_info(f"Updated drop-in config '{CFE_CONFIG}'")
        return Result.REPAIRED

    def restart_sshd(self) -> str:
        """Restart the sshd service if it is currently running."""
        r = subprocess.run(
            ["systemctl", "is-active", "--quiet", "sshd"],
        )
        if r.returncode != 0:
            # If sshd is not running, do nothing
            self.log_debug("The service sshd is not running")
            return Result.KEPT

        r = subprocess.run(
            ["systemctl", "restart", "--quiet", "sshd"],
        )
        if r.returncode != 0:
            self.log_error("Failed to restart sshd service")
            return Result.NOT_KEPT

        self.log_info("Restarted sshd service")
        return Result.REPAIRED

    def effective_config_has_directive(
        self, keyword: str, values: str | list[str]
    ) -> bool:
        """Check if the running sshd effective configuration (via sshd -T)
        contains the given directive(s) for a keyword."""
        r = subprocess.run(
            ["/usr/sbin/sshd", "-T"],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            self.log_error("Failed to get effective sshd config")
            return False
        effective = r.stdout.strip().splitlines()

        # sshd -T splits multi-argument keywords into separate
        # lines (e.g. "AllowUsers user1 user2" becomes two lines:
        # "allowusers user1" and "allowusers user2"), so we must
        # expand list values into individual directives to match
        # the effective config format for set comparison.

        for value in values if isinstance(values, list) else [values]:
            assert isinstance(value, str)
            directive = f"{keyword.lower()} {to_sshd_value(value)}"
            if directive in effective:
                self.log_debug(
                    f"Directive '{directive}' is present in effective sshd config"
                )
            else:
                self.log_debug(
                    f"Directive '{directive}' is NOT present in effective sshd config"
                )
                return False

        return True

    def verify_effective_config(self, keyword: str, values: str | list[str]) -> str:
        """Verify the effective sshd config contains the expected directive,
        returning KEPT on success or NOT_KEPT on failure."""
        if self.effective_config_has_directive(keyword, values):
            self.log_verbose("Successfully verified effective sshd config")
            return Result.KEPT

        self.log_error("Failed to verify effective sshd config")
        return Result.NOT_KEPT

    def evaluate_promise(
        self, promiser: str, attributes: dict[str, object], metadata: dict[str, str]
    ) -> str:
        assert "value" in attributes, "expected 'value' in attributes"
        value = attributes["value"]
        assert isinstance(value, (str, list)), "expected type str or list"
        assert value, "expected non-empty str or list"

        # Check if the effective config already has the desired state
        if self.effective_config_has_directive(promiser, value):
            return Result.KEPT

        # Ensure the base config includes the drop-in directory
        result = update_result(Result.KEPT, self.ensure_include_directive())

        # Ensure the drop-in directory exists
        result = update_result(result, self.ensure_drop_in_dir())

        # Ensure the drop-in config file contains the desired directive
        result = update_result(result, self.ensure_drop_in_config(promiser, value))

        # Restart sshd only if configuration was changed
        if result == Result.REPAIRED:
            result = update_result(result, self.restart_sshd())

        # Verify the effective config matches the desired state
        result = update_result(result, self.verify_effective_config(promiser, value))

        return result


if __name__ == "__main__":
    SshdPromiseTypeModule().start()
