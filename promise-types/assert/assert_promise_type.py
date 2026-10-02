#!/usr/bin/env python3
import difflib
import os
import subprocess

from cfengine_module_library import PromiseModule, ValidationError, Result

SUBJECT_ATTRIBUTES = {
    "int",
    "real",
    "str",
    "file",
    "dir",
    "command",
    "slist",
    "ilist",
    "rlist",
}
CHECKS_BY_SUBJECT = {
    "int": {"equals", "greater_than", "less_than"},
    "real": {"equals", "greater_than", "less_than"},
    "str": {"equals", "not_equals", "contains"},
    "file": {"exists", "perms", "contents"},
    "dir": {"exists"},
    "command": {"output"},
    "slist": {"equals", "contains"},
    "ilist": {"equals", "contains"},
    "rlist": {"equals", "contains"},
}
BOOLEAN_ATTRIBUTES = {"exists"}
LIST_SUBJECTS = {"slist", "ilist", "rlist"}


class CheckFailed(Exception):
    pass


class AssertModule(PromiseModule):
    def __init__(self):
        super().__init__("assert_promise_module", "0.1.0")

    def validate_promise(self, promiser, attributes, metadata):
        subjects_given = sorted(SUBJECT_ATTRIBUTES.intersection(attributes))

        if len(subjects_given) > 1:
            raise ValidationError(
                "Each assert: promise needs at most one of {}, got {}".format(
                    sorted(SUBJECT_ATTRIBUTES), subjects_given
                )
            )

        if not subjects_given:
            # No subject -- this promise exists to be gated by `if`/`unless`
            # (cf-agent only sends it to us at all when that condition
            # holds), so reaching here should pass by default, unless told
            # otherwise with `pass => "false"`.
            if "pass" in attributes and attributes["pass"] not in ("true", "false"):
                raise ValidationError(
                    "'pass' must be 'true' or 'false', got '{}'".format(
                        attributes["pass"]
                    )
                )
            unknown_attributes = set(attributes) - {"pass"}
            if unknown_attributes:
                raise ValidationError(
                    "A subjectless assert: promise only takes 'pass', got {}".format(
                        sorted(unknown_attributes)
                    )
                )
            return

        if "pass" in attributes:
            raise ValidationError(
                "'pass' can't be combined with a subject ('{}')".format(
                    subjects_given[0]
                )
            )

        subject = subjects_given[0]
        allowed_checks = CHECKS_BY_SUBJECT[subject]

        unknown_attributes = set(attributes) - {subject} - allowed_checks
        if unknown_attributes:
            raise ValidationError(
                "'{}' doesn't take {}".format(subject, sorted(unknown_attributes))
            )

        checks_given = allowed_checks.intersection(attributes)
        if subject != "command" and not checks_given:
            raise ValidationError(
                "'{}' needs at least one of {}".format(subject, sorted(allowed_checks))
            )

        for name in checks_given.intersection(BOOLEAN_ATTRIBUTES):
            if attributes[name] not in ("true", "false"):
                raise ValidationError(
                    "'{}' must be 'true' or 'false', got '{}'".format(
                        name, attributes[name]
                    )
                )

        # cf-agent doesn't type-check custom promise attributes itself, so a
        # bare scalar here (e.g. "$(x)" instead of "@(x)") would silently
        # misbehave rather than fail -- Python's `in` iterates a str's
        # characters, so a wrong-typed slist could even give a false PASS.
        if subject in LIST_SUBJECTS:
            for name in (subject, "equals"):
                if name in attributes and not isinstance(attributes[name], list):
                    raise ValidationError(
                        "'{}' must be a list, got {!r}".format(name, attributes[name])
                    )

    def evaluate_promise(self, promiser, attributes, metadata):
        if not SUBJECT_ATTRIBUTES.intersection(attributes):
            if attributes.get("pass", "true") == "true":
                self.log_info("[ASSERT] PASS {}".format(promiser))
                return Result.KEPT
            self.log_error("[ASSERT] FAIL {} # pass => false".format(promiser))
            return Result.NOT_KEPT
        try:
            check_subject(attributes)
        except CheckFailed as failure:
            self.log_error("[ASSERT] FAIL {} # {}".format(promiser, failure))
            return Result.NOT_KEPT
        self.log_info("[ASSERT] PASS {}".format(promiser))
        return Result.KEPT


def check_subject(attributes):
    if "int" in attributes:
        check_number(attributes, "int")
    elif "real" in attributes:
        check_number(attributes, "real")
    elif "str" in attributes:
        check_string(attributes)
    elif "file" in attributes:
        check_file(attributes)
    elif "dir" in attributes:
        check_directory(attributes)
    elif "command" in attributes:
        check_command(attributes)
    elif "slist" in attributes:
        check_list(attributes, "slist")
    elif "ilist" in attributes:
        check_list(attributes, "ilist")
    elif "rlist" in attributes:
        check_list(attributes, "rlist")


def parse_number(raw_value, subject_name):
    # CFEngine's own numeric functions (e.g. eval()) return whole numbers as
    # strings like "7.000000", so this always parses as a float first; "int"
    # additionally rejects a non-whole result and is then converted to an
    # actual int, so it compares and prints as "7", not "7.0".
    try:
        value = float(raw_value)
    except ValueError:
        raise CheckFailed("'{}' is not a valid {}".format(raw_value, subject_name))
    if subject_name != "int":
        return value
    if not value.is_integer():
        raise CheckFailed("'{}' is not a valid int".format(raw_value))
    return int(value)


def check_number(attributes, subject_name):
    actual = parse_number(attributes[subject_name], subject_name)

    if "equals" in attributes:
        expected = parse_number(attributes["equals"], subject_name)
        if actual != expected:
            raise CheckFailed("expected {}, got {}".format(expected, actual))

    if "greater_than" in attributes:
        threshold = parse_number(attributes["greater_than"], subject_name)
        if not actual > threshold:
            raise CheckFailed("{} is not greater than {}".format(actual, threshold))

    if "less_than" in attributes:
        threshold = parse_number(attributes["less_than"], subject_name)
        if not actual < threshold:
            raise CheckFailed("{} is not less than {}".format(actual, threshold))


def check_string(attributes):
    actual = attributes["str"]

    if "equals" in attributes and actual != attributes["equals"]:
        raise CheckFailed(
            "expected {!r}, got {!r}".format(attributes["equals"], actual)
        )

    if "not_equals" in attributes and actual == attributes["not_equals"]:
        raise CheckFailed(
            "expected not {!r}, but got it".format(attributes["not_equals"])
        )

    if "contains" in attributes and attributes["contains"] not in actual:
        raise CheckFailed(
            "{!r} does not contain {!r}".format(actual, attributes["contains"])
        )


def check_file(attributes):
    path = attributes["file"]

    if "exists" in attributes:
        should_exist = attributes["exists"] == "true"
        actually_exists = os.path.isfile(path)
        if actually_exists != should_exist:
            raise CheckFailed(
                "expected exists={}, but exists={}: {}".format(
                    should_exist, actually_exists, path
                )
            )

    if ("perms" in attributes or "contents" in attributes) and not os.path.isfile(path):
        raise CheckFailed("'{}' does not exist".format(path))

    if "perms" in attributes:
        expected_perms = attributes["perms"].lstrip("0") or "0"
        try:
            actual_perms = oct(os.stat(path).st_mode & 0o7777)[2:]
        except OSError as error:
            raise CheckFailed(str(error))
        if actual_perms != expected_perms:
            raise CheckFailed(
                "{} has permissions {}, expected {}".format(
                    path, actual_perms, expected_perms
                )
            )

    if "contents" in attributes:
        try:
            with open(path) as file:
                actual_contents = file.read()
        except OSError as error:
            raise CheckFailed(str(error))
        expected_contents = attributes["contents"]
        if actual_contents != expected_contents:
            diff = "\n".join(
                difflib.unified_diff(
                    expected_contents.splitlines(),
                    actual_contents.splitlines(),
                    fromfile="expected",
                    tofile="actual",
                    lineterm="",
                )
            )
            raise CheckFailed(
                "{} contents did not match the expected contents\n{}".format(path, diff)
            )


def check_directory(attributes):
    path = attributes["dir"]
    should_exist = attributes["exists"] == "true"
    actually_exists = os.path.isdir(path)
    if actually_exists != should_exist:
        raise CheckFailed(
            "expected exists={}, but exists={} for {}".format(
                should_exist, actually_exists, path
            )
        )


def check_list(attributes, subject_name):
    # ilist/rlist elements arrive as strings just like int/real do (e.g.
    # "5" and "5.000000" are the same rlist value in different renderings),
    # so they're compared numerically rather than as raw strings; slist
    # elements are compared as-is.
    def element_value(raw):
        if subject_name == "ilist":
            return parse_number(raw, "int")
        if subject_name == "rlist":
            return parse_number(raw, "real")
        return raw

    actual_values = [element_value(item) for item in attributes[subject_name]]

    if "equals" in attributes:
        expected_values = [element_value(item) for item in attributes["equals"]]
        if actual_values != expected_values:
            raise CheckFailed(
                "expected {!r}, got {!r}".format(expected_values, actual_values)
            )

    if "contains" in attributes:
        # A single value checks for that one element; a list checks that
        # every element of it is present (an "all of" check).
        requested = attributes["contains"]
        is_list = isinstance(requested, list)
        requested_values = [
            element_value(item) for item in (requested if is_list else [requested])
        ]
        missing = [value for value in requested_values if value not in actual_values]
        if missing:
            shown = missing if is_list else missing[0]
            raise CheckFailed("{!r} does not contain {!r}".format(actual_values, shown))


def check_command(attributes):
    command = attributes["command"]
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        raise CheckFailed("'{}' timed out".format(command))

    if result.returncode != 0:
        raise CheckFailed("'{}' exited {}".format(command, result.returncode))

    if "output" in attributes:
        combined_output = result.stdout + result.stderr
        if attributes["output"] not in combined_output:
            raise CheckFailed(
                "{} does not contain {!r}".format(
                    combined_output.strip(), attributes["output"]
                )
            )


if __name__ == "__main__":
    AssertModule().start()
