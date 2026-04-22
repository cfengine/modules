import sys
import os
import pytest
from unittest.mock import MagicMock

# Add library path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "..", "libraries", "python")
)
# Add module path
sys.path.insert(0, os.path.dirname(__file__))

# Mock dnf module before importing the promise module
mock_dnf = MagicMock()
mock_dnf.exceptions = MagicMock()
sys.modules["dnf"] = mock_dnf
sys.modules["dnf.exceptions"] = mock_dnf.exceptions

import appstreams as appstreams_module  # noqa: E402

appstreams_module.dnf = mock_dnf

from appstreams import AppStreamsPromiseTypeModule  # noqa: E402
from cfengine_module_library import ValidationError, Result  # noqa: E402


@pytest.fixture
def module():
    # Reset mocks
    mock_dnf.reset_mock()
    if hasattr(mock_dnf.Base, "return_value"):
        mock_dnf.Base.return_value.reset_mock()

    mod = AppStreamsPromiseTypeModule()
    mod._log_level = "info"
    mod._out = MagicMock()
    return mod


@pytest.fixture
def mock_mpc():
    # Setup the ModulePackageContainer mock
    mpc = MagicMock()
    # Setup constants
    mpc.ModuleState_ENABLED = 1
    mpc.ModuleState_DISABLED = 2
    mpc.ModuleState_INSTALLED = 3
    mpc.ModuleState_DEFAULT = 0
    return mpc


@pytest.fixture
def mock_base(mock_mpc):
    base = mock_dnf.Base.return_value
    base.sack._moduleContainer = mock_mpc
    return base


def test_harness_setup(module):
    """Verify the test harness is working"""
    assert module is not None
    assert module.name == "appstreams_promise_module"


def test_enable_module_already_enabled(module, mock_base, mock_mpc):
    """Test enabling a module that is already enabled (KEPT)"""
    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_ENABLED
    mock_mpc.getEnabledStream.return_value = "12"

    result = module.evaluate_promise("nodejs", {"state": "enabled", "stream": "12"}, {})
    assert result == Result.KEPT


def test_enable_module_repaired(module, mock_base, mock_mpc):
    """Test enabling a module that is disabled (REPAIRED)"""
    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_DISABLED
    mock_mpc.isEnabled.return_value = True  # After enable() called

    result = module.evaluate_promise("nodejs", {"state": "enabled", "stream": "12"}, {})

    mock_mpc.enable.assert_called_with("nodejs", "12")
    assert result == Result.REPAIRED


def test_disable_module_already_disabled(module, mock_base, mock_mpc):
    """Test disabling a module that is already disabled (KEPT)"""
    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_DISABLED

    result = module.evaluate_promise(
        "nodejs", {"state": "disabled", "stream": "12"}, {}
    )
    assert result == Result.KEPT


def test_disable_module_repaired(module, mock_base, mock_mpc):
    """Test disabling a module that is enabled (REPAIRED)"""
    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_ENABLED
    mock_mpc.isDisabled.return_value = True  # After disable() called

    result = module.evaluate_promise(
        "nodejs", {"state": "disabled", "stream": "12"}, {}
    )

    mock_mpc.disable.assert_called_with("nodejs")
    assert result == Result.REPAIRED


def test_install_profile_repaired(module, mock_base, mock_mpc):
    """Test installing a specific profile using 'installed' state (REPAIRED)"""
    # Initial state: enabled but not fully installed with profile
    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_ENABLED
    mock_mpc.getEnabledStream.return_value = "12"
    # First call (pre-install check) returns [], second call (post-install verify) returns ["common"]
    mock_mpc.getInstalledProfiles.side_effect = [[], ["common"]]

    result = module.evaluate_promise(
        "nodejs", {"state": "installed", "stream": "12", "profile": "common"}, {}
    )

    # We now use ModuleBase API instead of mpc.install
    # Verify the transaction was executed
    mock_base.resolve.assert_called()
    mock_base.do_transaction.assert_called()
    assert result == Result.REPAIRED


def test_remove_module_repaired(module, mock_base, mock_mpc):
    """Test removing a module using 'removed' state (REPAIRED)"""
    # First call (current state check) returns INSTALLED, second (post-remove verify) returns DEFAULT
    mock_mpc.getModuleState.side_effect = [
        mock_mpc.ModuleState_INSTALLED,
        mock_mpc.ModuleState_DEFAULT,
    ]
    mock_mpc.getEnabledStream.return_value = "12"
    mock_mpc.getInstalledProfiles.return_value = ["common"]

    # For removal, we also need package query to mock explicit package removal
    mock_module_obj = MagicMock()
    mock_module_obj.getStream.return_value = "12"
    mock_profile_obj = MagicMock()
    mock_profile_obj.getName.return_value = "common"
    mock_profile_obj.getContent.return_value = ["pkg1"]
    mock_module_obj.getProfiles.return_value = [mock_profile_obj]
    mock_mpc.query.return_value = [mock_module_obj]

    result = module.evaluate_promise("nodejs", {"state": "removed", "stream": "12"}, {})

    # Logic in _remove_module calls uninstall for each installed profile if no profile specified
    mock_mpc.uninstall.assert_called()
    assert result == Result.REPAIRED


def test_install_profile_idempotency_success(module, mock_base, mock_mpc):
    """Test installing a profile that is already present (KEPT)"""
    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_INSTALLED
    mock_mpc.getEnabledStream.return_value = "12"
    mock_mpc.getInstalledProfiles.return_value = ["common"]

    result = module.evaluate_promise(
        "nodejs", {"state": "installed", "stream": "12", "profile": "common"}, {}
    )

    assert result == Result.KEPT


def test_reset_module_repaired(module, mock_base, mock_mpc):
    """Test resetting a module to default state (REPAIRED)"""
    # evaluate_promise calls _get_module_state first, then _reset_module calls it twice more
    mock_mpc.getModuleState.side_effect = [
        mock_mpc.ModuleState_ENABLED,  # evaluate_promise current-state check
        mock_mpc.ModuleState_ENABLED,  # _reset_module early-exit check
        mock_mpc.ModuleState_DEFAULT,  # _reset_module post-reset verification
    ]

    result = module.evaluate_promise("nodejs", {"state": "default", "stream": "12"}, {})

    mock_mpc.reset.assert_called_with("nodejs")
    assert result == Result.REPAIRED


def test_stream_default_resolution(module, mock_base, mock_mpc):
    """Test resolving stream => 'default'"""
    mock_mpc.getDefaultStream.return_value = "12"

    # State check uses resolved stream
    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_ENABLED
    mock_mpc.getEnabledStream.return_value = "12"

    result = module.evaluate_promise(
        "nodejs", {"state": "enabled", "stream": "default"}, {}
    )

    assert result == Result.KEPT


def test_profile_default_resolution(module, mock_base, mock_mpc):
    """Test resolving profile => 'default'"""
    mock_mpc.getDefaultStream.return_value = "12"
    mock_mpc.getDefaultProfiles.return_value = ["default_prof"]

    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_INSTALLED
    mock_mpc.getEnabledStream.return_value = "12"
    mock_mpc.getInstalledProfiles.return_value = ["default_prof"]

    result = module.evaluate_promise(
        "nodejs", {"state": "installed", "stream": "12", "profile": "default"}, {}
    )

    assert result == Result.KEPT


def test_invalid_aliases(module):
    """Verify that aliases 'install' and 'remove' are invalid"""

    # Test 'install'
    with pytest.raises(ValidationError):
        module._validate_state("install")

    # Test 'remove'
    with pytest.raises(ValidationError):
        module._validate_state("remove")


def test_get_module_state_logic(module, mock_mpc):
    """Test the logic of _get_module_state"""
    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_ENABLED
    assert module._get_module_state(mock_mpc, "nodejs") == "enabled"

    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_DISABLED
    assert module._get_module_state(mock_mpc, "nodejs") == "disabled"

    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_INSTALLED
    assert module._get_module_state(mock_mpc, "nodejs") == "installed"

    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_DEFAULT
    assert module._get_module_state(mock_mpc, "nodejs") == "removed"

    mock_mpc.getModuleState.return_value = 999  # Unknown state
    assert module._get_module_state(mock_mpc, "nodejs") == "removed"


def test_remove_already_removed(module, mock_base, mock_mpc):
    """Test removing a module that is already removed (KEPT)"""
    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_DEFAULT
    result = module.evaluate_promise("nodejs", {"state": "removed"}, {})
    assert result == Result.KEPT


def test_remove_already_disabled(module, mock_base, mock_mpc):
    """Test removing a module that is already disabled (KEPT)"""
    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_DISABLED
    result = module.evaluate_promise("nodejs", {"state": "removed"}, {})
    assert result == Result.KEPT


def test_enable_wrong_stream_repaired(module, mock_base, mock_mpc):
    """Test enabling a module that is enabled but with wrong stream (REPAIRED)"""
    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_ENABLED
    mock_mpc.getEnabledStream.return_value = "10"
    mock_mpc.isEnabled.return_value = True
    result = module.evaluate_promise("nodejs", {"state": "enabled", "stream": "12"}, {})
    mock_mpc.enable.assert_called_with("nodejs", "12")
    assert result == Result.REPAIRED


def test_stream_default_not_found(module, mock_base, mock_mpc):
    """Test stream => 'default' when no default stream exists (NOT_KEPT)"""
    mock_mpc.getDefaultStream.return_value = None
    result = module.evaluate_promise(
        "nodejs", {"state": "enabled", "stream": "default"}, {}
    )
    assert result == Result.NOT_KEPT


def test_profile_default_not_found(module, mock_base, mock_mpc):
    """Test profile => 'default' when no default profile exists (NOT_KEPT)"""
    mock_mpc.getDefaultStream.return_value = "12"
    mock_mpc.getDefaultProfiles.return_value = []
    result = module.evaluate_promise(
        "nodejs", {"state": "installed", "stream": "12", "profile": "default"}, {}
    )
    assert result == Result.NOT_KEPT


def test_remove_unknown_module_runtime_error(module, mock_base, mock_mpc):
    """Test removing a module when getEnabledStream raises RuntimeError"""
    mock_mpc.getModuleState.return_value = mock_mpc.ModuleState_ENABLED
    mock_mpc.getEnabledStream.side_effect = RuntimeError("No such module")
    result = module.evaluate_promise("unknown_mod", {"state": "removed"}, {})
    # With no stream and getEnabledStream failing, target_stream is None, so KEPT
    assert result == Result.KEPT
