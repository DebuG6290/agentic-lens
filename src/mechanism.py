"""Validation helpers for Lens mechanism objects.

The mechanism object is the contract between intent decomposition, retrieval,
and classification.  Legacy ``reasoning_paths`` objects are accepted so that
existing saved/debugged lenses do not stop working during the migration.
"""


REQUIRED_TOP_LEVEL_KEYS = ("entity", "user_context")


def _non_empty_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_mechanism(path) -> bool:
    if not isinstance(path, dict):
        return False
    if not _non_empty_text(path.get("id")):
        return False
    if not _non_empty_text(path.get("name")):
        return False
    if not isinstance(path.get("causal_chain"), list) or len(path["causal_chain"]) < 2:
        return False
    if not all(_non_empty_text(step) for step in path["causal_chain"]):
        return False
    if not isinstance(path.get("signals"), list) or not path["signals"]:
        return False
    if not all(_non_empty_text(signal) for signal in path["signals"]):
        return False
    for key in ("affected_assets", "exclusions"):
        if key in path and not isinstance(path[key], list):
            return False
    return True


def is_mechanism_object(candidate) -> bool:
    """Return whether *candidate* is a valid current or legacy object."""
    if not isinstance(candidate, dict):
        return False
    if not all(_non_empty_text(candidate.get(key)) for key in REQUIRED_TOP_LEVEL_KEYS):
        return False

    mechanisms = candidate.get("mechanisms")
    if isinstance(mechanisms, list) and mechanisms:
        return all(_valid_mechanism(path) for path in mechanisms)

    # Compatibility with v1 objects already produced by the original prompt.
    paths = candidate.get("reasoning_paths")
    return isinstance(paths, list) and bool(paths) and all(
        isinstance(path, dict)
        and _non_empty_text(path.get("path"))
        and isinstance(path.get("keywords"), list)
        and bool(path["keywords"])
        for path in paths
    )


def mechanism_signals(mechanism_object: dict) -> list[str]:
    """Collect retrieval signals from current or legacy mechanism objects."""
    signals = []
    paths = mechanism_object.get("mechanisms") or mechanism_object.get("reasoning_paths") or []
    for path in paths:
        values = path.get("signals", path.get("keywords", []))
        for value in values or []:
            value = str(value).strip()
            if value and value.casefold() not in {item.casefold() for item in signals}:
                signals.append(value)
    return signals
