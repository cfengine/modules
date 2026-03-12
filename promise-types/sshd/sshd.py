import os
import re
import sys
import subprocess
import tempfile

try:
    from cfengine_module_library import PromiseModule, ValidationError, Result
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "../../libraries/python"))
    from cfengine_module_library import PromiseModule, ValidationError, Result


BASE_CONFIG = "/etc/ssh/sshd_config"
DROP_IN_DIR = "/etc/ssh/sshd_config.d/"
CFE_CONFIG = os.path.join(DROP_IN_DIR, "00-cfengine.conf")


def to_sshd_value(value: str | list[str]) -> str:
    """Convert a Python value to an sshd config value. Lists are space-joined,
    strings with spaces are quoted."""
    match value:
        case list():
            return " ".join(value)
        case str():
            return f'"{value}"' if " " in value else value


def safe_write(path: str, lines: list[str]) -> None:
    """Atomically write lines to a file via a temporary file in the same directory."""
    dir = os.path.dirname(path)
    base = os.path.basename(path)
    prefix, suffix = os.path.splitext(base)

    fd, tmp_path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=dir)
    try:
        os.fchmod(fd, 0o600)  # rw-------
        with os.fdopen(fd, "w") as f:
            f.writelines(lines)
        os.replace(tmp_path, path)
    except BaseException:
        # BaseException (not Exception) to also clean up on KeyboardInterrupt/SystemExit
        os.unlink(tmp_path)
        raise


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


def normalize_directive(directive: str) -> str:
    """Normalize a directive by removing trailing comments and replacing = with a space."""
    # Remove trailing comment
    directive = re.sub(r"\s*#.*$", "", directive)
    # Normalize separator (= or whitespace) to a single space
    directive = re.sub(r"\s*=\s*", " ", directive, count=1)
    return directive.strip().lower()


def get_directives(lines: list[str]) -> set[str]:
    """Extract and normalize all non-comment, non-empty directives from lines."""
    return {
        normalize_directive(line)
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    }


def has_same_directives(a: list[str], b: list[str]) -> bool:
    """Check if two sets of lines contain the same directives, ignoring comments and order."""
    return get_directives(a) == get_directives(b)


def get_first_directive(lines: list[str]) -> tuple[str | None, int]:
    """Return the first non-comment, non-empty directive and its index.
    Returns (None, len(lines)) if no directive is found."""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return (stripped, i)
    return (None, len(lines))


class SshdPromiseTypeModule(PromiseModule):

    def validate_promise(  # pyright: ignore[reportImplicitOverride]
        self, promiser: str, attributes: dict[str, object], metadata: dict[str, str]
    ):
        for attr, value in attributes.items():
            if not isinstance(value, (str, list)):
                raise ValidationError(f"Attribute '{attr}' must be a string or slist")

    def ensure_include_directive(self) -> str:
        """Ensure the base sshd config includes the drop-in directory."""
        try:
            with open(BASE_CONFIG, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            self.log_error(  # pyright: ignore[reportUnknownMemberType]
                f"Base configuration file '{BASE_CONFIG}' does not exist"
            )
            return Result.NOT_KEPT

        first_directive, index = get_first_directive(lines)

        if first_directive is None or not is_drop_in_directive(first_directive):
            drop_in_dir = DROP_IN_DIR
            include_directive = f"Include {drop_in_dir}/*.conf"

            self.log_debug(  # pyright: ignore[reportUnknownMemberType]
                f"Expected first non-comment line in '{BASE_CONFIG}' to be '{include_directive}'"
            )

            lines.insert(index, f"{include_directive } # Added by CFEngine\n")
            try:
                safe_write(BASE_CONFIG, lines)
            except Exception as e:
                self.log_error(  # pyright: ignore[reportUnknownMemberType]
                    f"Failed to write '{BASE_CONFIG}': {e}"
                )
                return Result.NOT_KEPT

            self.log_info(  # pyright: ignore[reportUnknownMemberType]
                f"Added include directive to '{BASE_CONFIG}'"
            )
            return Result.REPAIRED

        return Result.KEPT

    def ensure_drop_in_dir(self) -> str:
        """Ensure the drop-in config directory exists."""
        if os.path.isdir(DROP_IN_DIR):
            return Result.KEPT

        try:
            os.makedirs(DROP_IN_DIR, mode=0o755)  # rwxr-xr-x
        except Exception as e:
            self.log_error(  # pyright: ignore[reportUnknownMemberType]
                f"Failed to create drop-in directory '{DROP_IN_DIR}': {e}"
            )
            return Result.NOT_KEPT

        self.log_info(  # pyright: ignore[reportUnknownMemberType]
            f"Created drop-in directory '{DROP_IN_DIR}'"
        )
        return Result.REPAIRED

    def ensure_drop_in_config(self, attributes: dict[str, object]) -> str:
        """Write the CFEngine drop-in config file with the given attributes."""
        lines = ["# Managed by CFEngine\n"]
        for attr, value in attributes.items():
            # Ensured by validate_promise
            assert isinstance(value, (str, list))
            lines.append(
                f"{attr} {to_sshd_value(value)}\n"  # pyright: ignore[reportUnknownArgumentType]
            )

        try:
            with open(CFE_CONFIG, "r") as f:
                existing = f.readlines()
        except FileNotFoundError:
            existing = []

        if has_same_directives(lines, existing):
            return Result.KEPT

        try:
            safe_write(CFE_CONFIG, lines)
        except Exception as e:
            self.log_error(  # pyright: ignore[reportUnknownMemberType]
                f"Failed to write drop-in config '{CFE_CONFIG}': {e}"
            )
            return Result.NOT_KEPT

        self.log_info(  # pyright: ignore[reportUnknownMemberType]
            f"Updated drop-in config '{CFE_CONFIG}'"
        )
        return Result.REPAIRED

    def restart_sshd(self) -> str:
        """Restart the sshd service if it is currently running."""
        r = subprocess.run(
            ["systemctl", "is-active", "--quiet", "sshd"],
        )
        if r.returncode != 0:
            # If sshd is not running, do nothing
            self.log_debug(  # pyright: ignore[reportUnknownMemberType]
                "The service sshd is not running"
            )
            return Result.KEPT

        r = subprocess.run(
            ["systemctl", "restart", "--quiet", "sshd"],
        )
        if r.returncode != 0:
            self.log_error(  # pyright: ignore[reportUnknownMemberType]
                "Failed to restart sshd service"
            )
            return Result.NOT_KEPT

        self.log_info(  # pyright: ignore[reportUnknownMemberType]
            "Restarted sshd service"
        )
        return Result.REPAIRED

    def verify_effective_config(self, attributes: dict[str, object]) -> str:
        """Verify that the desired attributes appear in the effective sshd config."""
        r = subprocess.run(
            ["/usr/sbin/sshd", "-T"],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            self.log_error(  # pyright: ignore[reportUnknownMemberType]
                "Failed to retrieve effective sshd configuration"
            )
            return Result.NOT_KEPT

        effective = get_directives(r.stdout.splitlines())

        desired: list[str] = []
        for attr, value in attributes.items():
            # Ensured by validate_promise
            assert isinstance(value, (str, list))
            desired.append(f"{attr} {to_sshd_value(value)}")  # pyright: ignore[reportUnknownArgumentType]

        missing = get_directives(desired) - effective
        if missing:
            self.log_error(  # pyright: ignore[reportUnknownMemberType]
                f"Missing directives in effective sshd config: {missing}"
            )
            return Result.NOT_KEPT

        return Result.KEPT


    def evaluate_promise(  # pyright: ignore[reportImplicitOverride]
        self, promiser: str, attributes: dict[str, object], metadata: dict[str, str]
    ) -> str:
        result = Result.KEPT

        # Step 1: Ensure the base config includes the drop-in directory
        result = update_result(result, self.ensure_include_directive())

        # Step 2: Ensure the drop-in directory exists
        result = update_result(result, self.ensure_drop_in_dir())

        # Step 3: Ensure the drop-in config file contains the desired attributes
        result = update_result(result, self.ensure_drop_in_config(attributes))

        # Step 4: Restart sshd only if configuration was changed
        if result == Result.REPAIRED:
            result = update_result(result, self.restart_sshd())

        # Step 5: Verify the effective config matches the desired attributes
        result = update_result(result, self.verify_effective_config(attributes))

        return result


def test_to_sshd_value_str():
    assert to_sshd_value("no") == "no"


def test_to_sshd_value_str_with_spaces():
    assert to_sshd_value("some value") == '"some value"'


def test_to_sshd_value_list():
    assert to_sshd_value(["user1", "user2"]) == "user1 user2"


def test_get_first_directive():
    lines = ["# comment\n", "PermitRootLogin no\n", "Port 22\n"]
    assert get_first_directive(lines) == ("PermitRootLogin no", 1)


def test_get_first_directive_no_comments():
    lines = ["PermitRootLogin no\n", "Port 22\n"]
    assert get_first_directive(lines) == ("PermitRootLogin no", 0)


def test_get_first_directive_all_comments():
    lines = ["# comment\n", "# another comment\n"]
    assert get_first_directive(lines) == (None, 2)


def test_get_first_directive_empty():
    assert get_first_directive([]) == (None, 0)


def test_get_first_directive_extra_whitespace():
    lines = ["# comment\n", "PermitRootLogin  no\n"]
    assert get_first_directive(lines) == ("PermitRootLogin  no", 1)


def test_get_first_directive_equal_sign():
    lines = ["# comment\n", "PermitRootLogin=no\n"]
    assert get_first_directive(lines) == ("PermitRootLogin=no", 1)


def test_get_first_directive_blank_lines():
    lines = ["\n", "  \n", "# comment\n", "Port 22\n"]
    assert get_first_directive(lines) == ("Port 22", 3)


def test_normalize_directive_simple():
    assert normalize_directive("permitrootlogin no") == "permitrootlogin no"


def test_normalize_directive_trailing_comment():
    assert normalize_directive("PermitRootLogin no # comment") == "permitrootlogin no"


def test_normalize_directive_equal_sign():
    assert normalize_directive("PermitRootLogin=no") == "permitrootlogin no"


def test_normalize_directive_space_equal_space():
    assert normalize_directive("PermitRootLogin = no") == "permitrootlogin no"


def test_normalize_directive_equal_and_comment():
    assert normalize_directive("PermitRootLogin=no # comment") == "permitrootlogin no"


def test_normalize_directive_leading_trailing_whitespace():
    assert normalize_directive("  PermitRootLogin no  ") == "permitrootlogin no"


def test_get_directives_filters_comments():
    lines = ["# comment\n", "PermitRootLogin no\n", "Port 22\n"]
    assert get_directives(lines) == {"permitrootlogin no", "port 22"}


def test_get_directives_filters_blank_lines():
    lines = ["\n", "PermitRootLogin no\n", "  \n"]
    assert get_directives(lines) == {"permitrootlogin no"}


def test_get_directives_normalizes():
    lines = ["PermitRootLogin=no # managed\n", "Port 22\n"]
    assert get_directives(lines) == {"permitrootlogin no", "port 22"}


def test_get_directives_empty():
    assert get_directives([]) == set()


def test_has_same_directives_same():
    a = ["# comment\n", "PermitRootLogin no\n", "Port 22\n"]
    b = ["Port 22\n", "PermitRootLogin no\n"]
    assert has_same_directives(a, b)


def test_has_same_directives_different_comments():
    a = ["# managed by X\n", "PermitRootLogin no\n"]
    b = ["# managed by Y\n", "PermitRootLogin no\n"]
    assert has_same_directives(a, b)


def test_has_same_directives_different_format():
    a = ["PermitRootLogin=no # comment\n"]
    b = ["PermitRootLogin no\n"]
    assert has_same_directives(a, b)


def test_has_same_directives_missing():
    a = ["PermitRootLogin no\n", "Port 22\n"]
    b = ["PermitRootLogin no\n"]
    assert not has_same_directives(a, b)


def test_has_same_directives_extra():
    a = ["PermitRootLogin no\n"]
    b = ["PermitRootLogin no\n", "Port 22\n"]
    assert not has_same_directives(a, b)


def test_is_drop_in_directive_space():
    assert is_drop_in_directive(f"Include {DROP_IN_DIR}*.conf")


def test_is_drop_in_directive_equal():
    assert is_drop_in_directive(f"Include={DROP_IN_DIR}*.conf")


def test_is_drop_in_directive_space_equal_space():
    assert is_drop_in_directive(f"Include = {DROP_IN_DIR}*.conf")


def test_is_drop_in_directive_case_insensitive():
    assert is_drop_in_directive(f"include {DROP_IN_DIR}*.conf")


def test_is_drop_in_directive_extra_files():
    assert is_drop_in_directive(f"Include {DROP_IN_DIR}*.conf /other/path")


def test_is_drop_in_directive_wrong_path():
    assert not is_drop_in_directive("Include /other/path/*.conf")


def test_is_drop_in_directive_no_separator():
    assert not is_drop_in_directive(f"Include{DROP_IN_DIR}*.conf")


def test_is_drop_in_directive_not_include():
    assert not is_drop_in_directive("permitrootlogin no")


def test_update_result_kept_kept():
    assert update_result(Result.KEPT, Result.KEPT) == Result.KEPT


def test_update_result_kept_repaired():
    assert update_result(Result.KEPT, Result.REPAIRED) == Result.REPAIRED


def test_update_result_kept_not_kept():
    assert update_result(Result.KEPT, Result.NOT_KEPT) == Result.NOT_KEPT


def test_update_result_repaired_kept():
    assert update_result(Result.REPAIRED, Result.KEPT) == Result.REPAIRED


def test_update_result_repaired_repaired():
    assert update_result(Result.REPAIRED, Result.REPAIRED) == Result.REPAIRED


def test_update_result_repaired_not_kept():
    assert update_result(Result.REPAIRED, Result.NOT_KEPT) == Result.NOT_KEPT


def test_update_result_not_kept_kept():
    assert update_result(Result.NOT_KEPT, Result.KEPT) == Result.NOT_KEPT


def test_update_result_not_kept_repaired():
    assert update_result(Result.NOT_KEPT, Result.REPAIRED) == Result.NOT_KEPT


def test_update_result_not_kept_not_kept():
    assert update_result(Result.NOT_KEPT, Result.NOT_KEPT) == Result.NOT_KEPT



if __name__ == "__main__":
    SshdPromiseTypeModule().start()  # pyright: ignore[reportUnknownMemberType]
