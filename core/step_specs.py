"""Code-first step specifications and content loading helpers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import load_toml_config
from .errors import ConfigError


SUPPORTED_STEP_MODES = {
    "accept",
    "text",
    "choice",
    "rating",
    "selection",
    "iterative_selection",
    "edit",
    "progress",
    "multi_field_form",
    "card_builder",
    "generate",
}


@dataclass(frozen=True)
class ActionSpec:
    """Reusable action wiring owned by Python step definitions."""

    name: str
    trigger: str | None = None
    enabled: bool | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def as_config(self) -> dict[str, Any]:
        config = {"name": self.name} | deepcopy(self.params)
        if self.trigger is not None:
            config["trigger"] = self.trigger
        if self.enabled is not None:
            config["enabled"] = self.enabled
        return config


@dataclass(frozen=True)
class StepSpec:
    """Code-defined runtime contract for a step."""

    id: str
    mode: str
    content_path: str | Path
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    ui: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    before_actions: tuple[ActionSpec, ...] = ()
    after_actions: tuple[ActionSpec, ...] = ()

    def build_config(self) -> dict[str, Any]:
        if self.mode not in SUPPORTED_STEP_MODES:
            raise ConfigError(f"Unsupported step mode '{self.mode}'")

        content = load_step_content(self.content_path)
        config = {key: deepcopy(value) for key, value in content.items() if key not in {"step", "state", "before_actions", "after_actions", "model"}}
        config["step"] = {"id": self.id, "mode": self.mode}
        config["state"] = {"reads": list(self.reads), "writes": list(self.writes)}
        config["ui"] = deepcopy(content.get("ui", {})) | deepcopy(self.ui)
        config["before_actions"] = [action.as_config() for action in self.before_actions]
        config["after_actions"] = [action.as_config() for action in self.after_actions]
        if self.model is not None:
            config["model"] = self.model
        return config


def load_step_content(content_path: str | Path) -> dict[str, Any]:
    """Load a content-only TOML file for a step."""
    path = Path(content_path)
    if not path.exists():
        raise ConfigError(f"Step content file not found: {path}")
    content = load_toml_config(path)
    if not isinstance(content, dict):
        raise ConfigError(f"Step content file must load into a dictionary: {path}")
    return content


def accept_step(
    step_id: str,
    content_path: str | Path,
    *,
    response_key: str | None = None,
    reads: tuple[str, ...] = (),
    writes: tuple[str, ...] = (),
    before_actions: tuple[ActionSpec, ...] = (),
    ui: dict[str, Any] | None = None,
) -> StepSpec:
    ui_config = dict(ui or {})
    if response_key:
        ui_config["response_key"] = response_key
    return StepSpec(
        id=step_id,
        mode="accept",
        content_path=content_path,
        reads=reads,
        writes=writes,
        ui=ui_config,
        before_actions=before_actions,
    )


def text_input_step(
    step_id: str,
    content_path: str | Path,
    *,
    response_key: str,
    reads: tuple[str, ...],
    writes: tuple[str, ...],
) -> StepSpec:
    return StepSpec(
        id=step_id,
        mode="text",
        content_path=content_path,
        reads=reads,
        writes=writes,
        ui={"response_key": response_key},
    )


def chat_step(
    step_id: str,
    content_path: str | Path,
    *,
    transcript_key: str,
    response_key: str,
    reads: tuple[str, ...],
    writes: tuple[str, ...],
    model: str,
    before_actions: tuple[ActionSpec, ...],
    after_actions: tuple[ActionSpec, ...],
) -> StepSpec:
    return StepSpec(
        id=step_id,
        mode="text",
        content_path=content_path,
        reads=reads,
        writes=writes,
        ui={
            "input_style": "chat",
            "transcript_key": transcript_key,
            "response_key": response_key,
        },
        model=model,
        before_actions=before_actions,
        after_actions=after_actions,
    )


def selection_step(
    step_id: str,
    content_path: str | Path,
    *,
    options_key: str,
    selected_index_key: str,
    response_key: str,
    reads: tuple[str, ...],
    writes: tuple[str, ...],
    ui: dict[str, Any] | None = None,
) -> StepSpec:
    ui_config = {
        "options_state_key": options_key,
        "selected_index_key": selected_index_key,
        "response_key": response_key,
    }
    ui_config |= dict(ui or {})
    return StepSpec(
        id=step_id,
        mode="selection",
        content_path=content_path,
        reads=reads,
        writes=writes,
        ui=ui_config,
    )


def iterative_selection_step(
    step_id: str,
    content_path: str | Path,
    *,
    options_key: str,
    selected_index_key: str,
    response_key: str,
    reads: tuple[str, ...],
    writes: tuple[str, ...],
) -> StepSpec:
    return StepSpec(
        id=step_id,
        mode="iterative_selection",
        content_path=content_path,
        reads=reads,
        writes=writes,
        ui={
            "options_state_key": options_key,
            "selected_index_key": selected_index_key,
            "response_key": response_key,
        },
    )


def rating_step(
    step_id: str,
    content_path: str | Path,
    *,
    display_state_key: str,
    response_key: str,
    reads: tuple[str, ...],
    writes: tuple[str, ...],
) -> StepSpec:
    return StepSpec(
        id=step_id,
        mode="rating",
        content_path=content_path,
        reads=reads,
        writes=writes,
        ui={
            "display_state_key": display_state_key,
            "response_key": response_key,
        },
    )


def edit_step(
    step_id: str,
    content_path: str | Path,
    *,
    current_key: str,
    original_key: str,
    suggestion_key: str,
    request_key: str,
    history_key: str | None = None,
    reads: tuple[str, ...],
    writes: tuple[str, ...],
    model: str,
    after_actions: tuple[ActionSpec, ...],
) -> StepSpec:
    ui_config = {
        "response_key": current_key,
        "original_state_key": original_key,
        "suggestion_state_key": suggestion_key,
        "request_key": request_key,
    }
    if history_key is not None:
        ui_config["history_key"] = history_key
    return StepSpec(
        id=step_id,
        mode="edit",
        content_path=content_path,
        reads=reads,
        writes=writes,
        ui=ui_config,
        model=model,
        after_actions=after_actions,
    )


def multi_field_form_step(
    step_id: str,
    content_path: str | Path,
    *,
    reads: tuple[str, ...],
    writes: tuple[str, ...],
    display_state_key: str | None = None,
    display_state_keys: tuple[str, ...] | None = None,
    fields: tuple[dict[str, Any], ...] | None = None,
    validator: Any | None = None,
) -> StepSpec:
    ui: dict[str, Any] = {}
    if display_state_key is not None:
        ui["display_state_key"] = display_state_key
    if display_state_keys is not None:
        ui["context_state_keys"] = list(display_state_keys)
    if fields is not None:
        ui["fields"] = [deepcopy(field) for field in fields]
    if validator is not None:
        ui["validator"] = validator
    return StepSpec(
        id=step_id,
        mode="multi_field_form",
        content_path=content_path,
        reads=reads,
        writes=writes,
        ui=ui,
    )


def card_builder_step(
    step_id: str,
    content_path: str | Path,
    *,
    answers_key: str,
    card_key: str,
    reads: tuple[str, ...],
    writes: tuple[str, ...],
    context_state_keys: tuple[str, ...] | None = None,
    after_actions: tuple[ActionSpec, ...] = (),
) -> StepSpec:
    ui: dict[str, Any] = {
        "answers_key": answers_key,
        "card_key": card_key,
    }
    if context_state_keys is not None:
        ui["context_state_keys"] = list(context_state_keys)
    return StepSpec(
        id=step_id,
        mode="card_builder",
        content_path=content_path,
        reads=reads,
        writes=writes,
        ui=ui,
        after_actions=after_actions,
    )


def generate_step(
    step_id: str,
    content_path: str | Path,
    *,
    output_key: str,
    reads: tuple[str, ...],
    writes: tuple[str, ...],
    context_state_keys: tuple[str, ...] | None = None,
    after_actions: tuple[ActionSpec, ...] = (),
) -> StepSpec:
    ui: dict[str, Any] = {"output_key": output_key}
    if context_state_keys is not None:
        ui["context_state_keys"] = list(context_state_keys)
    return StepSpec(
        id=step_id,
        mode="generate",
        content_path=content_path,
        reads=reads,
        writes=writes,
        ui=ui,
        after_actions=after_actions,
    )
