"""backend/tests/unit/test_capability_registry.py

Unit tests for the Capability Registry.

Issue #62 acceptance criteria:
  - Register a mock capability, verify it appears in get_capability_list()
  - get_capability("registered_name") returns the correct callable
  - get_capability("unknown") returns None
  - Duplicate name raises CapabilityRegistrationError
"""

import pytest

import app.orchestration.capability_registry as registry_module
from app.exceptions import CapabilityRegistrationError
from app.orchestration.capability_registry import (
    get_capability,
    get_capability_list,
    register_capability,
)


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the registry before and after every test for isolation."""
    registry_module._REGISTRY.clear()
    yield
    registry_module._REGISTRY.clear()


# ── Happy paths ───────────────────────────────────────────────────────

def test_register_mock_capability_appears_in_list() -> None:
    """Registered capability appears in get_capability_list() without 'fn' key."""

    @register_capability(
        name="mock_capability",
        description="A mock capability for testing",
        input_schema={},
        output_schema={},
    )
    async def mock_fn(params: dict):
        pass

    cap_list = get_capability_list()
    assert len(cap_list) == 1
    assert cap_list[0]["name"] == "mock_capability"
    assert cap_list[0]["description"] == "A mock capability for testing"
    assert "fn" not in cap_list[0]  # fn must be stripped


def test_get_capability_returns_correct_callable() -> None:
    """get_capability returns the exact function that was registered."""

    @register_capability(
        name="lookup_test",
        description="Test lookup",
        input_schema={},
        output_schema={},
    )
    async def lookup_fn(params: dict):
        pass

    result = get_capability("lookup_test")
    assert result is lookup_fn


def test_get_capability_unknown_returns_none() -> None:
    """get_capability returns None for an unregistered name."""
    assert get_capability("unknown_capability") is None


# ── Unhappy paths ─────────────────────────────────────────────────────

def test_duplicate_name_raises_capability_registration_error() -> None:
    """Registering two capabilities with the same name raises CapabilityRegistrationError."""

    @register_capability(
        name="duplicate",
        description="First",
        input_schema={},
        output_schema={},
    )
    async def first_fn(params: dict):
        pass

    with pytest.raises(CapabilityRegistrationError):

        @register_capability(
            name="duplicate",
            description="Second",
            input_schema={},
            output_schema={},
        )
        async def second_fn(params: dict):
            pass