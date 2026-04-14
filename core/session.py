"""Shared session/context helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import streamlit as st


@dataclass
class AppContext:
    """Thin wrapper over Streamlit session state for shared app data."""

    namespace: str

    def _prefix(self, key: str) -> str:
        return f"{self.namespace}.{key}"

    def init_defaults(self, defaults: dict[str, Any]) -> None:
        for key, value in defaults.items():
            full_key = self._prefix(key)
            if full_key not in st.session_state:
                st.session_state[full_key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return st.session_state.get(self._prefix(key), default)

    def set(self, key: str, value: Any) -> None:
        st.session_state[self._prefix(key)] = value

    def update(self, values: dict[str, Any]) -> None:
        for key, value in values.items():
            self.set(key, value)

    def append_message(self, key: str, message: dict[str, Any]) -> None:
        items = list(self.get(key, []))
        items.append(message)
        self.set(key, items)

    def clear_many(self, keys: Iterable[str]) -> None:
        for key in keys:
            full_key = self._prefix(key)
            if full_key in st.session_state:
                del st.session_state[full_key]

    def items(self) -> dict[str, Any]:
        """Return this namespace's session-state items without the namespace prefix."""
        prefix = f"{self.namespace}."
        values: dict[str, Any] = {}
        for key, value in st.session_state.items():
            if key.startswith(prefix):
                values[key[len(prefix):]] = value
        return values
