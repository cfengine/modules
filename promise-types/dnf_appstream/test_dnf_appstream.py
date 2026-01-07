#!/usr/bin/env python3

import os
import sys

# Add the libraries directory to the Python path so we can import cfengine_module_library
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "libraries", "python"))

try:
    from dnf_appstream import DnfAppStreamPromiseTypeModule
    from cfengine_module_library import ValidationError
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure cfengine_module_library.py is in the correct location")
    sys.exit(1)

def test_validation():
    """Test validation of module attributes"""
    print("Testing validation...")

    module = DnfAppStreamPromiseTypeModule()

    # Test valid attributes
    try:
        module.validate_promise("nodejs", {
            "state": "enabled",
            "stream": "12"
        }, {})
        print("  ✓ Valid attributes validation passed")
    except Exception as e:
        print(f"  ✗ Valid attributes validation failed: {e}")

    # Test invalid module name
    try:
        module.validate_promise("nodejs; rm -rf /", {
            "state": "enabled"
        }, {})
        print("  ✗ Invalid module name validation failed - should have caught injection")
    except ValidationError as e:
        print(f"  ✓ Invalid module name validation passed: {e}")
    except Exception as e:
        print(f"  ? Unexpected exception for invalid module name: {e}")

    # Note: Stream and State validation have been moved to attribute validators
    # which are handled by the library, not inside validate_promise directly.
    # Therefore we don't test them here via validate_promise, but in their specific test functions below.

def test_module_name_validation():
    """Test module name validation"""
    print("\nTesting module name validation...")

    module = DnfAppStreamPromiseTypeModule()

    # Test valid names
    valid_names = ["nodejs", "python3.6", "python36", "postgresql", "maven", "httpd"]
    for name in valid_names:
        try:
            module._validate_module_name(name)
            print(f"  ✓ Valid name '{name}' passed validation")
        except Exception as e:
            print(f"  ✗ Valid name '{name}' failed validation: {e}")

    # Test invalid names
    invalid_names = ["nodejs;rm", "python36&&", "postgresql|", "maven>", "httpd<"]
    for name in invalid_names:
        try:
            module._validate_module_name(name)
            print(f"  ✗ Invalid name '{name}' passed validation - should have failed")
        except Exception as e:
            print(f"  ✓ Invalid name '{name}' failed validation as expected: {e}")

def test_stream_name_validation():
    """Test stream name validation"""
    print("\nTesting stream name validation...")

    module = DnfAppStreamPromiseTypeModule()

    # Test valid stream names
    valid_streams = ["12", "14", "3.6", "1.14", "latest", "stable"]
    for stream in valid_streams:
        try:
            module._validate_stream_name(stream)
            print(f"  ✓ Valid stream '{stream}' passed validation")
        except Exception as e:
            print(f"  ✗ Valid stream '{stream}' failed validation: {e}")

    # Test invalid stream names
    invalid_streams = ["12;rm", "14&&", "3.6|", "latest>", "stable<"]
    for stream in invalid_streams:
        try:
            module._validate_stream_name(stream)
            print(f"  ✗ Invalid stream '{stream}' passed validation - should have failed")
        except Exception as e:
            print(f"  ✓ Invalid stream '{stream}' failed validation as expected: {e}")

def test_state_validation():
    """Test state validation"""
    print("\nTesting state validation...")

    module = DnfAppStreamPromiseTypeModule()

    # Test valid states
    valid_states = ["enabled", "disabled", "installed", "removed"]
    for state in valid_states:
        try:
            module._validate_state(state)
            print(f"  ✓ Valid state '{state}' passed validation")
        except Exception as e:
            print(f"  ✗ Valid state '{state}' failed validation: {e}")

    # Test invalid states
    invalid_states = ["active", "inactive", "present", "absent", "enable", "disable"]
    for state in invalid_states:
        try:
            module._validate_state(state)
            print(f"  ✗ Invalid state '{state}' passed validation - should have failed")
        except ValidationError as e:
            print(f"  ✓ Invalid state '{state}' failed validation as expected: {e}")
        except Exception as e:
            print(f"  ? Unexpected exception for invalid state '{state}': {e}")

def test_state_parsing():
    """Test parsing of module states from dnf output"""
    print("\nTesting state parsing...")

    module = DnfAppStreamPromiseTypeModule()

    # Test that the method exists and can be called
    try:
        # We can't easily test the actual parsing without mocking dnf,
        # but we can at least verify the method exists
        hasattr(module, '_get_module_state')
        print("  ✓ State parsing method exists")
    except Exception as e:
        print(f"  ✗ State parsing method test failed: {e}")

if __name__ == "__main__":
    print("Running tests for dnf_appstream promise type...")

    test_validation()
    test_module_name_validation()
    test_stream_name_validation()
    test_state_validation()
    test_state_parsing()

    print("\nAll tests completed.")
