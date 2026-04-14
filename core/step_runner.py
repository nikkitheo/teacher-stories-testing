"""Common bot-step runtime."""

from __future__ import annotations

from typing import Any

import streamlit as st

from bot_actions import run_action

from .errors import ConfigError
from .renderers import _interpolate_state, _render_chat_transcript, render_mode
from .state_keys import pick_state_key
from .step_specs import StepSpec


def run_step(step_spec: StepSpec, *, context, services: dict[str, Any]) -> dict[str, Any]:
    """Run a bot step and return its current status."""
    config = step_spec.build_config()
    step = config["step"]
    step_id = step["id"]

    if _is_post_chat_phase(config, context, step_id):
        return _run_post_chat_phase(config, context=context, services=services, step_id=step_id)

    _run_before_actions(config, context, services, step_id)
    event = render_mode(config, context, step_id, services=services)
    if event is None:
        return {"status": "waiting", "step_id": step_id}

    _apply_updates(context, config, event.get("updates", {}))
    if event.get("defer_after_actions"):
        return {"status": "waiting", "step_id": step_id, "rerun": True}

    action_result = _run_after_actions(config, context, services, step_id, event["event"])
    if event["event"] == "post_chat_process":
        context.set(f"__system__.{step_id}.post_chat_processing", False)
        context.set(f"__system__.{step_id}.post_chat_ready", True)
        return {"status": "waiting", "step_id": step_id, "rerun": True}

    complete = bool(event.get("complete", False))
    if action_result.get("step_complete") is False:
        complete = False
    elif action_result.get("step_complete") is True:
        complete = True

    if action_result.get("rerun"):
        return {"status": "waiting", "step_id": step_id, "rerun": True}

    if complete:
        return {"status": "completed", "step_id": step_id, "event": event["event"]}

    if event.get("updates") or action_result.get("updates"):
        return {"status": "waiting", "step_id": step_id, "rerun": True}

    return {"status": "waiting", "step_id": step_id}


def _run_before_actions(config: dict, context, services: dict[str, Any], step_id: str) -> None:
    meta_key = f"__step_runtime__.{step_id}.before_done"
    if context.get(meta_key, False):
        return
    for action in config.get("before_actions", []):
        result = run_action(action, config=config, context=context, services=services)
        _apply_updates(context, config, result.get("updates", {}))
    context.set(meta_key, True)


def _run_after_actions(config: dict, context, services: dict[str, Any], step_id: str, trigger: str) -> dict[str, Any]:
    combined = {"updates": {}, "rerun": False}
    for action in config.get("after_actions", []):
        action_trigger = action.get("trigger", "submit")
        if action_trigger != trigger:
            continue
        result = run_action(action, config=config, context=context, services=services)
        updates = result.get("updates", {})
        _apply_updates(context, config, updates)
        combined["updates"] |= updates
        if result.get("rerun"):
            combined["rerun"] = True
        if "step_complete" in result:
            combined["step_complete"] = result["step_complete"]
    return combined


def _is_post_chat_phase(config: dict, context, step_id: str) -> bool:
    return (
        config["step"]["mode"] == "text"
        and config.get("ui", {}).get("input_style") == "chat"
        and bool(config.get("ui", {}).get("post_chat"))
        and bool(context.get(f"__system__.{step_id}.chat_finished", False))
    )


def _run_post_chat_phase(config: dict, *, context, services: dict[str, Any], step_id: str) -> dict[str, Any]:
    ui = config.get("ui", {})
    state = config.get("state", {})
    post_chat = dict(ui.get("post_chat", {}))
    _render_heading_and_body(ui, context)

    transcript_key = pick_state_key(
        state,
        explicit=ui.get("transcript_key"),
        suffixes=("transcript",),
        exact="transcript",
        fallback="transcript",
    )
    messages = context.get(transcript_key, [])
    appended_ai_message = None
    if post_chat.get("assistant_message"):
        appended_ai_message = _interpolate_state(post_chat["assistant_message"], context)
    _render_chat_transcript(messages, appended_ai_message=appended_ai_message)

    ready_state_key = pick_state_key(
        state,
        explicit=post_chat.get("ready_state_key"),
        suffixes=("generated_scenarios", "generated_narratives", "generated_options"),
        exact="generated_scenarios",
    )
    ready_key = f"__system__.{step_id}.post_chat_ready"
    processing_key = f"__system__.{step_id}.post_chat_processing"
    continue_key = f"__system__.{step_id}.post_chat_continue"
    disabled_placeholder = post_chat.get("disabled_input_placeholder", "This conversation is complete.")

    if context.get(continue_key, False):
        context.set(continue_key, False)
        return {"status": "completed", "step_id": step_id, "event": "submit"}

    ready = bool(context.get(ready_key, False))
    if ready_state_key:
        ready = ready or bool(context.get(ready_state_key))

    st.chat_input(disabled_placeholder, key=f"{step_id}.chat_input_disabled", disabled=True)

    with st.container(border=True):
        if ready:
            st.progress(100, text=post_chat.get("ready_text", "Your narratives are ready."))
            if st.button(post_chat.get("button_label", "Show the narratives"), key=f"{step_id}.post_chat_ready"):
                context.set(continue_key, True)
                st.rerun()
        else:
            progress_bar = st.progress(0, text=post_chat.get("loading_text", "Generating your narratives..."))
            context.set(processing_key, True)
            try:
                _run_after_actions(config, context, services, step_id, "post_chat_process")
            finally:
                context.set(processing_key, False)
            progress_bar.progress(100, text=post_chat.get("ready_text", "Your narratives are ready."))
            context.set(ready_key, True)
            st.rerun()
    return {"status": "waiting", "step_id": step_id}


def _render_heading_and_body(ui: dict, context) -> None:
    title = ui.get("title")
    if title:
        st.markdown(f"#### {title}")
    intro = ui.get("intro")
    if intro:
        st.markdown(_interpolate_state(intro, context), unsafe_allow_html=True)
    body = ui.get("body")
    if body:
        st.markdown(_interpolate_state(body, context), unsafe_allow_html=True)


def _apply_updates(context, config: dict, updates: dict[str, Any]) -> None:
    allowed = set(config["state"]["writes"]) | set(config["state"].get("reads", []))
    allowed |= {"__system__"}
    for key, value in updates.items():
        if key.startswith("__system__.") or key in allowed:
            context.set(key, value)
            continue
        raise ConfigError(f"Step '{config['step']['id']}' attempted to write undeclared state key '{key}'")
