"""backend/app/orchestration/capability_registry.py

Module-level Capability Registry.
Capabilities self-register via @register_capability at import time.
Assessment reads the list; Dispatch looks up callables by name.

Issue #62: Capability Registry — @register_capability decorator and dynamic lookup
"""

from collections.abc import Callable

from app.exceptions import CapabilityRegistrationError

# Plain module-level dict — no class, no dependency injection.
# Import order determines registration order.
_REGISTRY: dict[str, dict] = {}


def register_capability(
    name: str,
    description: str,
    input_schema: dict,
    output_schema: dict,
) -> Callable:
    """Decorator factory: register an async capability function.

    Args:
        name: Unique capability identifier (used by Assessment + Dispatch).
        description: Human-readable description (included in Assessment prompt).
        input_schema: JSON-schema dict describing the params the function accepts.
        output_schema: JSON-schema dict describing the AgentCall output.

    Returns:
        Decorator that registers the function and returns it unchanged.

    Raises:
        CapabilityRegistrationError: If a capability with this name is already registered.
    """
    def decorator(fn: Callable) -> Callable:
        if name in _REGISTRY:
            raise CapabilityRegistrationError(
                f"Capability '{name}' is already registered. "
                "Duplicate registrations are not allowed."
            )
        _REGISTRY[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "fn": fn,
        }
        return fn

    return decorator


def get_capability_list() -> list[dict]:
    """Return all registered capabilities as name+description dicts.

    Strips the callable before returning — the prompt only needs name and description.

    Returns:
        List of {"name": str, "description": str} dicts, one per registered capability.
    """
    return [
        {"name": entry["name"], "description": entry["description"]}
        for entry in _REGISTRY.values()
    ]


def get_capability(name: str) -> Callable | None:
    """Look up a registered capability function by name.

    Args:
        name: The capability identifier to look up.

    Returns:
        The registered async callable, or None if not found.
    """
    entry = _REGISTRY.get(name)
    return entry["fn"] if entry is not None else None