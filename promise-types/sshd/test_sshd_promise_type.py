import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../../libraries/python"))

from cfengine_module_library import Result  # noqa: E402

from sshd_promise_type import (  # noqa: E402
    sshd_quote,
    to_sshd_value,
    get_first_directive,
    is_drop_in_directive,
    update_result,
    DROP_IN_DIR,
)


def test_sshd_quote_simple():
    assert sshd_quote("no") == "no"


def test_sshd_quote_empty():
    assert sshd_quote("") == '""'


def test_sshd_quote_space():
    assert sshd_quote("some value") == '"some value"'


def test_sshd_quote_tab():
    assert sshd_quote("some\tvalue") == '"some\tvalue"'


def test_sshd_quote_hash():
    assert sshd_quote("before#after") == '"before#after"'


def test_sshd_quote_double_quote():
    assert sshd_quote('say "hello"') == '"say \\"hello\\""'


def test_sshd_quote_backslash():
    assert sshd_quote("path\\to") == "path\\to"


def test_sshd_quote_backslash_and_space():
    assert sshd_quote("path\\to dir") == '"path\\\\to dir"'


def test_to_sshd_value_str():
    assert to_sshd_value("no") == "no"


def test_to_sshd_value_str_with_spaces():
    assert to_sshd_value("some value") == '"some value"'


def test_to_sshd_value_list():
    assert to_sshd_value(["user1", "user2"]) == "user1 user2"


def test_to_sshd_value_list_with_quoting():
    assert to_sshd_value(["user1", "user 2"]) == 'user1 "user 2"'


def test_get_first_directive():
    lines = ["# comment\n", "PermitRootLogin no\n", "Port 22\n"]
    assert get_first_directive(lines) == "PermitRootLogin no"


def test_get_first_directive_no_comments():
    lines = ["PermitRootLogin no\n", "Port 22\n"]
    assert get_first_directive(lines) == "PermitRootLogin no"


def test_get_first_directive_all_comments():
    lines = ["# comment\n", "# another comment\n"]
    assert get_first_directive(lines) is None


def test_get_first_directive_empty():
    assert get_first_directive([]) is None


def test_get_first_directive_extra_whitespace():
    lines = ["# comment\n", "PermitRootLogin  no\n"]
    assert get_first_directive(lines) == "PermitRootLogin  no"


def test_get_first_directive_equal_sign():
    lines = ["# comment\n", "PermitRootLogin=no\n"]
    assert get_first_directive(lines) == "PermitRootLogin=no"


def test_get_first_directive_blank_lines():
    lines = ["\n", "  \n", "# comment\n", "Port 22\n"]
    assert get_first_directive(lines) == "Port 22"


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
