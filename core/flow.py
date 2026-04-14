"""Thin flow helpers used by app.py files."""

from __future__ import annotations

from enum import Enum
from typing import Any

import streamlit as st


def init_flow_state(context, *, initial_step: Enum, defaults: dict[str, Any]) -> None:
    """Initialize shared flow state once per session."""
    context.init_defaults({"current_step": initial_step.value} | defaults)


def current_step(context, enum_cls: type[Enum]) -> Enum:
    """Return the current enum value stored in session state."""
    return enum_cls(context.get("current_step"))


def go_to_step(context, next_step: Enum, updates: dict[str, Any] | None = None) -> None:
    """Update context and rerun the Streamlit app."""
    if updates:
        context.update(updates)
    context.set("current_step", next_step.value)
    st.rerun()


def should_skip_adaptation(rating: int | None, *, max_rating: int) -> bool:
    """Return whether the adaptation step should be skipped."""
    return rating is not None and rating >= max_rating

