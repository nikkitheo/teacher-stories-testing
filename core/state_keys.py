"""Helpers for resolving conventional state bindings from step specs."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


def pick_state_key(
    state: dict[str, Any],
    *,
    explicit: str | None = None,
    source: str = "all",
    suffixes: tuple[str, ...] = (),
    exact: str | None = None,
    fallback: str | None = None,
    exclude: tuple[str | None, ...] = (),
    allow_single: bool = False,
) -> str | None:
    """Resolve a state key from declared reads/writes using common naming conventions."""
    if explicit:
        return explicit

    keys = _state_keys(state, source=source)
    excluded = {key for key in exclude if key}
    candidates = [key for key in keys if key not in excluded]

    if exact and exact in candidates:
        return exact

    suffix_matches = [
        key
        for key in candidates
        if any(key == suffix or key.endswith(f"_{suffix}") for suffix in suffixes)
    ]
    if len(suffix_matches) == 1:
        return suffix_matches[0]

    if allow_single and len(candidates) == 1:
        return candidates[0]

    if fallback is not None:
        return fallback
    return exact


def sync_editor_state(
    session_state: MutableMapping[str, Any],
    *,
    editor_key: str,
    source_key: str,
    current_text: str,
) -> None:
    """Keep the editor value in sync only when the backing state changes externally."""
    if editor_key not in session_state:
        session_state[editor_key] = current_text

    if source_key not in session_state:
        session_state[editor_key] = current_text
        session_state[source_key] = current_text
        return

    if session_state[source_key] != current_text:
        session_state[source_key] = current_text
        session_state[editor_key] = current_text


def _state_keys(state: dict[str, Any], *, source: str) -> list[str]:
    if source == "writes":
        return list(state.get("writes", []))
    if source == "reads":
        return list(state.get("reads", []))
    return list(dict.fromkeys([*state.get("writes", []), *state.get("reads", [])]))
