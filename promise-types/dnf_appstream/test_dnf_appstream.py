import sys
import os
import pytest
from unittest.mock import MagicMock

# Mock dnf module before importing the promise module
mock_dnf = MagicMock()
sys.modules["dnf"] = mock_dnf

# Add library path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "libraries", "python"))
# Add module path
sys.path.insert(0, os.path.dirname(__file__))

from dnf_appstream import DnfAppStreamPromiseTypeModule, ValidationError

@pytest.fixture
def module():
    return DnfAppStreamPromiseTypeModule()

def test_validation_valid_attributes(module):
    """Test validation of valid module attributes"""
    module.validate_promise("nodejs", {
        "state": "enabled",
        "stream": "12"
    }, {})

def test_validation_invalid_module_name(module):
    """Test validation of invalid module name"""
    with pytest.raises(ValidationError) as excinfo:
        module.validate_promise("nodejs; echo hi", {
            "state": "enabled"
        }, {})
    assert "Invalid module name" in str(excinfo.value)

@pytest.mark.parametrize("name", [
    "nodejs", "python3.6", "python36", "postgresql", "maven", "httpd"
])
def test_module_name_validation_valid(module, name):
    """Test module name validation with valid names"""
    module._validate_module_name(name)

@pytest.mark.parametrize("name", [
    "nodejs;echo", "python36&&", "postgresql|", "maven>", "httpd<"
])
def test_module_name_validation_invalid(module, name):
    """Test module name validation with invalid names"""
    with pytest.raises(ValidationError):
        module._validate_module_name(name)

@pytest.mark.parametrize("stream", [
    "12", "14", "3.6", "1.14", "latest", "stable", "default"
])
def test_stream_name_validation_valid(module, stream):
    """Test stream name validation with valid names"""
    module._validate_stream_name(stream)

@pytest.mark.parametrize("stream", [
    "12;echo", "14&&", "3.6|", "latest>", "stable<"
])
def test_stream_name_validation_invalid(module, stream):
    """Test stream name validation with invalid names"""
    with pytest.raises(ValidationError):
        module._validate_stream_name(stream)

@pytest.mark.parametrize("state", [
    "enabled", "disabled", "installed", "removed", "default", "reset"
])
def test_state_validation_valid(module, state):
    """Test state validation with valid states"""
    module._validate_state(state)

@pytest.mark.parametrize("state", [
    "active", "inactive", "enable", "disable",
    "install", "remove", "present", "absent"
])
def test_state_validation_invalid(module, state):
    """Test state validation with invalid states"""
    with pytest.raises(ValidationError):
        module._validate_state(state)

def test_state_parsing_method_exists(module):
    """Test that the state parsing method exists"""
    assert hasattr(module, '_get_module_state')
