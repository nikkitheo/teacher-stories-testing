"""Built-in renderers for bot-step interaction modes."""

from __future__ import annotations

from datetime import datetime, timezone
import random
from typing import Any

import streamlit as st

from bot_actions import run_action

from .state_keys import pick_state_key, sync_editor_state


def render_mode(config: dict, context, step_id: str, *, services: dict[str, Any]) -> dict[str, Any] | None:
    """Render the configured step mode and return a step event when submitted."""
    mode = config["step"]["mode"]
    ui = config.get("ui", {})
    state = config.get("state", {})

    renderer = {
        "accept": _render_accept,
        "text": _render_text,
        "choice": _render_choice,
        "rating": _render_rating,
        "selection": _render_selection,
        "iterative_selection": _render_iterative_selection,
        "edit": _render_edit,
        "progress": _render_progress,
        "multi_field_form": _render_multi_field_form,
        "card_builder": _render_card_builder,
        "generate": _render_generate,
    }[mode]
    return renderer(ui, state, context, step_id, config=config, services=services)


def _render_accept(ui: dict, state: dict, context, step_id: str, *, config: dict, services: dict[str, Any]) -> dict[str, Any] | None:
    _render_heading(ui)
    _render_body(ui, context)
    _render_context_entries(ui.get("context_state_keys"), context)
    closing = ui.get("closing")
    if closing:
        st.markdown(_interpolate_state(closing, context), unsafe_allow_html=True)
    button_label = ui.get("button_label")
    if not button_label:
        return None
    if st.button(button_label, key=f"{step_id}.accept"):
        response_key = ui.get("response_key")
        updates = {response_key: True} if response_key else {}
        return {"event": "submit", "updates": updates, "complete": True}
    return None


def _render_text(ui: dict, state: dict, context, step_id: str, *, config: dict, services: dict[str, Any]) -> dict[str, Any] | None:
    _render_heading(ui)
    _render_body(ui, context)
    input_style = ui.get("input_style", "single_input")

    if input_style == "chat":
        transcript_key = pick_state_key(
            state,
            explicit=ui.get("transcript_key"),
            suffixes=("transcript",),
            exact="transcript",
            fallback="transcript",
        )
        response_key = pick_state_key(
            state,
            explicit=ui.get("response_key"),
            source="writes",
            suffixes=("last_user_message",),
            exact="last_user_message",
            fallback="last_user_message",
        )
        pending_key = f"__system__.{step_id}.chat_pending"
        pending = bool(context.get(pending_key, False))
        user_message = None
        if not pending:
            user_message = st.chat_input(
                ui.get("input_placeholder", "Type your answer here..."),
                key=f"{step_id}.chat_input",
            )

        thinking_text = ui.get("thinking_text", "Thinking...")
        messages = context.get(transcript_key, [])
        _render_chat_transcript(
            messages,
            pending_message=context.get(response_key, "") if pending else None,
            thinking_text=thinking_text if pending or user_message else None,
            preview_user_message=user_message,
        )

        if pending:
            return {"event": "submit", "updates": {}, "complete": False}

        if user_message:
            return {
                "event": "submit",
                "updates": {response_key: user_message, pending_key: True},
                "complete": False,
                "defer_after_actions": True,
            }
        return None

    form_key = f"{step_id}.text_form"
    response_key = pick_state_key(
        state,
        explicit=ui.get("response_key"),
        source="writes",
        exact="response_text",
        fallback="response_text",
        allow_single=True,
    )
    with st.form(form_key):
        prompt = ui.get("prompt")
        if prompt:
            st.write(prompt)
        current_value = context.get(response_key, "")
        response_value = st.text_input(
            ui.get("input_label", "Your answer"),
            value=current_value,
            placeholder=ui.get("input_placeholder", ""),
        )
        submitted = st.form_submit_button(ui.get("button_label", "Continue"))
    if submitted and response_value.strip():
        return {"event": "submit", "updates": {response_key: response_value.strip()}, "complete": True}
    if submitted:
        st.warning("Please enter a value before continuing.")
    return None


def _render_chat_transcript(
    messages: list[dict[str, Any]],
    *,
    pending_message: str | None = None,
    thinking_text: str | None = None,
    preview_user_message: str | None = None,
    appended_ai_message: str | None = None,
) -> None:
    with st.container(border=True):
        for message in messages:
            role = "ai" if message["role"] == "assistant" else "human"
            if role == "ai":
                st.chat_message(role).markdown(message["content"], unsafe_allow_html=True)
            else:
                st.chat_message(role).write(message["content"])

        if preview_user_message:
            st.chat_message("human").write(preview_user_message)
        elif pending_message:
            st.chat_message("human").write(pending_message)

        if thinking_text:
            st.chat_message("ai").write(thinking_text)

        if appended_ai_message:
            st.chat_message("ai").markdown(appended_ai_message, unsafe_allow_html=True)


def _render_choice(ui: dict, state: dict, context, step_id: str, *, config: dict, services: dict[str, Any]) -> dict[str, Any] | None:
    _render_heading(ui)
    _render_body(ui, context)
    options = _resolve_options(ui, context)
    if not options:
        st.info("No choices available.")
        return None
    form_key = f"{step_id}.choice_form"
    with st.form(form_key):
        choice = st.radio(ui.get("prompt", "Choose one option"), options)
        submitted = st.form_submit_button(ui.get("button_label", "Continue"))
    if submitted:
        return {"event": "submit", "updates": {ui.get("response_key", "choice"): choice}, "complete": True}
    return None


def _render_rating(ui: dict, state: dict, context, step_id: str, *, config: dict, services: dict[str, Any]) -> dict[str, Any] | None:
    _render_heading(ui)
    _render_body(ui, context)
    display_key = pick_state_key(
        state,
        explicit=ui.get("display_state_key"),
        suffixes=("selected_scenario", "selected_narrative", "final_scenario", "final_narrative"),
    )
    response_key = pick_state_key(
        state,
        explicit=ui.get("response_key"),
        source="writes",
        suffixes=("rating",),
        exact="rating",
        fallback="rating",
    )
    min_rating = ui.get("min", 0)
    max_rating = ui.get("max", 10)
    default_rating = ui.get("default", min_rating)

    with st.container(border=True):
        if display_key:
            _render_value(context.get(display_key, ""))

        prompt = ui.get("prompt", "How close is this to what I want to say?")
        st.markdown(
            f"<div style='font-size:1.5em; font-weight:bold; font-style:italic;'>{prompt}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                "<div style=\"display: flex; justify-content: space-between; margin-top: -8px;\">"
                f"<span style=\"color: red;\">{ui.get('low_label', 'needs a lot of work')}</span>"
                f"<span style=\"color: green;\">{ui.get('high_label', 'this looks good')}</span>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        rating = st.slider(
            "Rate this scenario",
            min_value=min_rating,
            max_value=max_rating,
            value=default_rating,
            step=1,
            label_visibility="collapsed",
            format=" ",
            key=f"{step_id}.rating",
        )
        _, center_col, _ = st.columns([1, 2, 1])
        with center_col:
            if st.button(ui.get("button_label", "Continue"), key=f"{step_id}.rating_submit", use_container_width=True):
                return {"event": "submit", "updates": {response_key: rating}, "complete": True}
    return None


def _render_selection(ui: dict, state: dict, context, step_id: str, *, config: dict, services: dict[str, Any]) -> dict[str, Any] | None:
    _render_heading(ui)
    _render_context_entries(ui.get("context_state_keys"), context)
    intro = ui.get("intro")
    body = ui.get("body")
    selection_copy = "\n\n".join(
        part for part in (
            _interpolate_state(intro, context) if intro else "",
            _interpolate_state(body, context) if body else "",
        )
        if part
    )
    if selection_copy:
        st.chat_message("ai").markdown(selection_copy, unsafe_allow_html=True)
    selected_index_key = pick_state_key(
        state,
        explicit=ui.get("selected_index_key"),
        source="writes",
        suffixes=("selected_index",),
        exact="selected_index",
        fallback="selected_index",
    )
    response_key = pick_state_key(
        state,
        explicit=ui.get("response_key"),
        source="writes",
        suffixes=("selected_scenario", "selected_narrative", "selected_value"),
        exact="selected_value",
        fallback="selected_value",
    )
    options = _resolve_options(
        {
            "options": ui.get("options"),
            "options_state_key": pick_state_key(
                state,
                explicit=ui.get("options_state_key"),
                suffixes=("generated_scenarios", "generated_narratives", "generated_options"),
                exact="generated_options",
                fallback="generated_options",
            ),
        },
        context,
    )
    if not options:
        st.info(ui.get("empty_text", "Nothing to review yet."))
        return None
    if len(options) == 1 and ui.get("auto_select_single", True):
        return {
            "event": "submit",
            "updates": {
                selected_index_key: 0,
                response_key: options[0],
            },
            "complete": True,
        }
    previous_group = None
    for index, option in enumerate(options):
        current_group = option.get("group") if isinstance(option, dict) else None
        if current_group and current_group != previous_group:
            st.markdown(f"### {current_group}")
            previous_group = current_group
        with st.container(border=True):
            content_col, button_col = st.columns([3, 1])
            with content_col:
                if not (isinstance(option, dict) and option.get("group")):
                    st.markdown(f"#### {ui.get('option_title_prefix', 'Scenario')} {index + 1}")
                _render_selection_option(option)
            with button_col:
                if st.button(ui.get("button_label", "Use this"), key=f"{step_id}.selection.{index}", use_container_width=True):
                    return {
                        "event": "submit",
                        "updates": {
                            selected_index_key: index,
                            response_key: option,
                        },
                        "complete": True,
                    }
    return None


def _render_iterative_selection(ui: dict, state: dict, context, step_id: str, *, config: dict, services: dict[str, Any]) -> dict[str, Any] | None:
    _render_heading(ui)
    _render_body(ui, context)

    selected_index_key = pick_state_key(
        state,
        explicit=ui.get("selected_index_key"),
        source="writes",
        suffixes=("selected_index",),
        exact="selected_index",
        fallback="selected_index",
    )
    response_key = pick_state_key(
        state,
        explicit=ui.get("response_key"),
        source="writes",
        suffixes=("selected_scenario", "selected_narrative", "selected_value"),
        exact="selected_value",
        fallback="selected_value",
    )
    options = _resolve_options(
        {
            "options": ui.get("options"),
            "options_state_key": pick_state_key(
                state,
                explicit=ui.get("options_state_key"),
                suffixes=("generated_scenarios", "generated_narratives", "generated_options"),
                exact="generated_options",
                fallback="generated_options",
            ),
        },
        context,
    )
    if not options:
        st.info(ui.get("empty_text", "No options available."))
        return None

    current_index_key = f"__system__.{step_id}.iterative_selection.current_index"
    rejected_indices_key = f"__system__.{step_id}.iterative_selection.rejected_indices"
    rejected_indices = [
        int(index)
        for index in context.get(rejected_indices_key, [])
        if isinstance(index, int) and 0 <= index < len(options)
    ]
    available_indices = [index for index in range(len(options)) if index not in rejected_indices]

    if not available_indices:
        st.info(ui.get("exhausted_text", "No more options are available to review."))
        if st.button(ui.get("restart_button", "Start over"), key=f"{step_id}.iterative_selection.restart"):
            return {
                "event": "restart",
                "updates": {
                    current_index_key: None,
                    rejected_indices_key: [],
                },
                "complete": False,
            }
        return None

    current_index = context.get(current_index_key)
    if current_index not in available_indices:
        current_index = random.choice(available_indices)
        context.set(current_index_key, current_index)

    option = options[current_index]
    with st.container(border=True):
        title = ui.get("option_title")
        if title:
            st.markdown(f"#### {title}")
        _render_selection_option(option)

    reject_col, accept_col = st.columns(2)
    with reject_col:
        if st.button(ui.get("reject_button", "No"), key=f"{step_id}.iterative_selection.reject", use_container_width=True):
            return {
                "event": "reject",
                "updates": {
                    current_index_key: None,
                    rejected_indices_key: rejected_indices + [current_index],
                },
                "complete": False,
            }
    with accept_col:
        if st.button(ui.get("accept_button", "Yes"), key=f"{step_id}.iterative_selection.accept", use_container_width=True):
            return {
                "event": "submit",
                "updates": {
                    current_index_key: None,
                    rejected_indices_key: rejected_indices,
                    selected_index_key: current_index,
                    response_key: option,
                },
                "complete": True,
            }
    return None


def _render_edit(ui: dict, state: dict, context, step_id: str, *, config: dict, services: dict[str, Any]) -> dict[str, Any] | None:
    _render_heading(ui)
    _render_body(ui, context)

    current_key = pick_state_key(
        state,
        explicit=ui.get("response_key"),
        source="writes",
        suffixes=("final_scenario", "editable_text"),
        exact="editable_text",
        fallback="editable_text",
    )
    original_key = pick_state_key(
        state,
        explicit=ui.get("original_state_key"),
        suffixes=("selected_scenario", "selected_narrative"),
        exact="selected_scenario",
        fallback=current_key,
        exclude=(current_key,),
    )
    suggestion_key = pick_state_key(
        state,
        explicit=ui.get("suggestion_state_key"),
        suffixes=("suggested_scenario", "suggested_text"),
        exact="suggested_text",
        fallback="suggested_text",
        exclude=(current_key, original_key),
    )
    request_key = pick_state_key(
        state,
        explicit=ui.get("request_key"),
        source="writes",
        suffixes=("adaptation_request",),
        exact="adaptation_request",
        fallback="adaptation_request",
        exclude=(current_key, original_key, suggestion_key),
    )
    history_key = pick_state_key(
        state,
        explicit=ui.get("history_key"),
        source="writes",
        suffixes=("adaptation_history",),
        exact="adaptation_history",
        fallback=None,
        exclude=(current_key, original_key, suggestion_key, request_key),
    )
    editor_key = f"{step_id}.editor"
    editor_source_key = f"{editor_key}.__source"
    editor_override_key = f"__system__.{step_id}.editor_override"
    current_text = context.get(current_key, "")
    processing_key = f"__system__.{step_id}.adaptation_processing"
    messages_key = f"__system__.{step_id}.adaptation_messages"
    processing = bool(context.get(processing_key, False))
    editor_override = context.get(editor_override_key)
    if editor_override is not None:
        st.session_state[editor_key] = editor_override
        st.session_state[editor_source_key] = editor_override
        context.set(editor_override_key, None)
    sync_editor_state(
        st.session_state,
        editor_key=editor_key,
        source_key=editor_source_key,
        current_text=current_text,
    )

    st.divider()
    st.markdown(f"#### {ui.get('edit_title', 'Adapt yourself')} ✍️")
    edited_text = st.text_area(
        ui.get("input_label", "Edit"),
        key=editor_key,
        height=ui.get("height", 230),
        disabled=processing,
        label_visibility="collapsed",
    )
    suggestion = context.get(suggestion_key)

    _, reset_col, done_col, _ = st.columns([1, 2, 2, 1])
    with reset_col:
        if st.button(ui.get("reset_button", "Reset"), key=f"{step_id}.reset", disabled=processing, use_container_width=True):
            original_text = context.get(original_key, "")
            return {
                "event": "reset",
                "updates": {
                    current_key: original_text,
                    suggestion_key: None,
                    messages_key: [],
                    request_key: "",
                    editor_override_key: original_text,
                },
                "complete": False,
            }
    with done_col:
        if st.button(ui.get("done_button", "Continue"), key=f"{step_id}.done", disabled=processing, use_container_width=True):
            return {
                "event": "submit",
                "updates": {
                    current_key: edited_text,
                    suggestion_key: None,
                    messages_key: [],
                    request_key: "",
                    editor_override_key: edited_text,
                },
                "complete": True,
            }

    st.markdown("")
    with st.container(border=True):
        st.markdown(f"#### {ui.get('assistant_title', 'Adapt with AI')} 🦾")
        messages = list(context.get(messages_key, []))
        appended_ai_message = ui.get("assistant_intro", "What would you like to change?") if not messages else None
        _render_chat_transcript(
            messages,
            thinking_text=ui.get("thinking_text", "Thinking...") if processing else None,
            appended_ai_message=appended_ai_message,
        )

        if processing:
            try:
                with st.spinner(ui.get("processing_text", "Working on your updated scenario...")):
                    result = _run_step_actions_snapshot(config, context.items(), services, trigger="request_adaptation")
                for key, value in result.get("updates", {}).items():
                    context.set(key, value)
                suggestion = result.get("updates", {}).get(suggestion_key)
                if suggestion:
                    if history_key:
                        _append_adaptation_history_entry(
                            context,
                            history_key,
                            {
                                "request": context.get(request_key, ""),
                                "suggestion": suggestion,
                                "source_text": current_text,
                                "status": "suggested",
                                "requested_at": _timestamp_now(),
                            },
                        )
                    updated_messages = list(context.get(messages_key, []))
                    updated_messages.append({"role": "assistant", "content": suggestion})
                    context.set(messages_key, updated_messages)
            finally:
                context.set(processing_key, False)
                context.set(request_key, "")
            st.rerun()
            return None

        if suggestion:
            st.markdown("**What do you think?**")
            reject_col, accept_col = st.columns(2)
            with reject_col:
                if st.button(ui.get("reject_button", "Try again"), key=f"{step_id}.reject", use_container_width=True):
                    if history_key:
                        _update_latest_adaptation_history_entry(
                            context,
                            history_key,
                            {"status": "rejected", "decision_at": _timestamp_now()},
                        )
                    return {
                        "event": "reject_suggestion",
                        "updates": {
                            current_key: edited_text,
                            suggestion_key: None,
                            messages_key: [],
                            request_key: "",
                            editor_override_key: edited_text,
                        },
                        "complete": False,
                    }
            with accept_col:
                if st.button(ui.get("accept_button", "Use this version"), key=f"{step_id}.accept_suggestion", use_container_width=True):
                    if history_key:
                        _update_latest_adaptation_history_entry(
                            context,
                            history_key,
                            {"status": "accepted", "decision_at": _timestamp_now()},
                        )
                    return {
                        "event": "accept_suggestion",
                        "updates": {
                            current_key: suggestion,
                            suggestion_key: None,
                            messages_key: [],
                            request_key: "",
                            editor_override_key: suggestion,
                        },
                        "complete": False,
                    }
        else:
            request = st.chat_input(ui.get("input_placeholder", "Describe what you'd like to change..."))
            if request:
                messages.append({"role": "user", "content": request})
                return {
                    "event": "request_adaptation",
                    "updates": {
                        current_key: edited_text,
                        request_key: request,
                        processing_key: True,
                        messages_key: messages,
                    },
                    "complete": False,
                    "defer_after_actions": True,
                }
    return None


def _render_progress(ui: dict, state: dict, context, step_id: str, *, config: dict, services: dict[str, Any]) -> dict[str, Any] | None:
    ready_key = pick_state_key(
        state,
        explicit=ui.get("ready_state_key"),
        suffixes=("generated_scenarios", "generated_narratives", "generated_options"),
        exact="generated_scenarios",
        fallback="generated_scenarios",
    )
    done_key = f"__system__.{step_id}.progress_done"
    ready = bool(context.get(ready_key)) or bool(context.get(done_key, False))

    if ready:
        if st.button(ui.get("button_label", "Show the narratives"), key=f"{step_id}.ready"):
            return {"event": "submit", "updates": {}, "complete": True}
    return None


def _render_multi_field_form(ui: dict, state: dict, context, step_id: str, *, config: dict, services: dict[str, Any]) -> dict[str, Any] | None:
    _render_heading(ui)
    _render_body(ui, context)
    context_entries = ui.get("context_state_keys")
    if context_entries is None:
        explicit_display_key = ui.get("display_state_key")
        context_entries = [explicit_display_key] if explicit_display_key else []

    for index, entry in enumerate(context_entries):
        if isinstance(entry, dict):
            state_key = entry.get("key")
            title = entry.get("title")
            collapsible = bool(entry.get("collapsible", False))
            expanded = bool(entry.get("expanded", False))
        else:
            state_key = str(entry) if entry else None
            title = None
            collapsible = False
            expanded = False
        if not state_key:
            continue
        value = context.get(state_key, "")
        if value in ("", None, [], {}):
            continue
        if collapsible:
            with st.expander(title or state_key, expanded=expanded):
                _render_value(value)
        else:
            with st.container(border=True):
                if title:
                    st.markdown(f"**{title}**")
                _render_value(value)

    field_specs = list(ui.get("fields", []))

    updates: dict[str, Any] = {}
    validation_errors: list[str] = []

    with st.form(f"{step_id}.multi_field_form"):
        if not field_specs:
            st.warning("multi_field_form requires ui.fields.")
        for index, field in enumerate(field_specs):
            field_type = field.get("type", "").strip().lower()
            response_key = field.get("response_key")
            if not response_key:
                continue
            widget_suffix = field.get("widget_key") or response_key or str(index)
            widget_key = f"{step_id}.field.{widget_suffix}"

            if field_type == "rating":
                min_value = field.get("min", 0)
                max_value = field.get("max", 10)
                default_value = context.get(response_key, field.get("default", min_value))
                updates[response_key] = st.slider(
                    field.get("prompt", "Rate"),
                    min_value=min_value,
                    max_value=max_value,
                    value=default_value,
                    step=field.get("step", 1),
                    key=widget_key,
                )
                continue

            if field_type == "text":
                current_value = context.get(response_key, "")
                value = st.text_area(
                    field.get("input_label", "Your answer"),
                    value=current_value,
                    placeholder=field.get("input_placeholder", ""),
                    height=field.get("height", 180),
                    key=widget_key,
                )
                trimmed = value.strip()
                updates[response_key] = trimmed
                if field.get("required", True) and not trimmed:
                    validation_errors.append(field.get("required_message", "Please complete the written reflection before continuing."))
                continue

            if field_type == "single_choice":
                options = list(field.get("options", []))
                current_value = context.get(response_key)
                if current_value not in options:
                    current_value = None
                selected = st.radio(
                    field.get("prompt", field.get("input_label", "Choose one option")),
                    options,
                    index=options.index(current_value) if current_value in options else None,
                    key=widget_key,
                )
                updates[response_key] = selected
                if field.get("required", True) and not selected:
                    validation_errors.append(field.get("required_message", "Please select one option before continuing."))
                continue

            if field_type == "multiple_choice":
                options = list(field.get("options", []))
                current_value = context.get(response_key, [])
                if not isinstance(current_value, list):
                    current_value = []
                selected_values = st.multiselect(
                    field.get("prompt", field.get("input_label", "Select all that apply")),
                    options,
                    default=[value for value in current_value if value in options],
                    key=widget_key,
                )
                updates[response_key] = selected_values
                if field.get("required", True) and not selected_values:
                    validation_errors.append(field.get("required_message", "Please select at least one option before continuing."))
                continue

            if field_type == "grouped_checkbox":
                options = list(field.get("options", []))
                min_selections = int(field.get("min_selections", 1))
                current_selected = context.get(response_key, []) or []
                if not isinstance(current_selected, list):
                    current_selected = []
                selected_titles: list[str] = []
                previous_group = None
                for opt_index, option in enumerate(options):
                    if isinstance(option, str):
                        option = {"title": option}
                    elif not isinstance(option, dict):
                        st.warning(
                            f"grouped_checkbox option at index {opt_index} must be a string or dict, got {type(option).__name__}."
                        )
                        continue
                    current_group = option.get("group")
                    if current_group and current_group != previous_group:
                        st.markdown(f"### {current_group}")
                        previous_group = current_group
                    with st.container(border=True):
                        title = str(option.get("title", "") or "")
                        body = str(option.get("body", "") or "")
                        if not title:
                            st.warning(f"grouped_checkbox option at index {opt_index} is missing a title.")
                            continue
                        checked = st.checkbox(
                            f"**{title}**",
                            value=title in current_selected,
                            key=f"{widget_key}.{opt_index}",
                        )
                        if body:
                            st.markdown(body)
                        if checked:
                            selected_titles.append(title)
                updates[response_key] = selected_titles
                if field.get("required", True) and len(selected_titles) < min_selections:
                    validation_errors.append(
                        field.get(
                            "required_message",
                            f"Please select at least {min_selections} option(s) before continuing.",
                        )
                    )
                continue

            st.warning(f"Unsupported field type '{field_type}' in multi_field_form.")

        submitted = st.form_submit_button(ui.get("button_label", "Continue"))

    if submitted and not validation_errors:
        validator = ui.get("validator")
        if callable(validator):
            validation_result = validator(dict(updates), context)
            if isinstance(validation_result, str) and validation_result.strip():
                validation_errors.append(validation_result.strip())
            elif validation_result is False:
                validation_errors.append(ui.get("validation_error_message", "Please review your responses before continuing."))

    if submitted and not validation_errors:
        return {
            "event": "submit",
            "updates": updates,
            "complete": True,
        }
    if submitted and validation_errors:
        st.warning(validation_errors[0])
    return None


def _render_card_builder(ui: dict, state: dict, context, step_id: str, *, config: dict, services: dict[str, Any]) -> dict[str, Any] | None:
    _render_heading(ui)
    _render_body(ui, context)
    context_entries = ui.get("context_state_keys", [])
    for entry in context_entries:
        if isinstance(entry, dict):
            state_key = entry.get("key")
            title = entry.get("title")
        else:
            state_key = str(entry) if entry else None
            title = None
        if not state_key:
            continue
        value = context.get(state_key, "")
        if value in ("", None, [], {}):
            continue
        with st.container(border=True):
            if title:
                st.markdown(f"**{title}**")
            _render_value(value)

    answers_key = pick_state_key(
        state,
        explicit=ui.get("answers_key"),
        source="writes",
        suffixes=("card_answers",),
        exact="card_answers",
        fallback="card_answers",
    )
    card_key = pick_state_key(
        state,
        explicit=ui.get("card_key"),
        suffixes=("generated_card",),
        exact="generated_card",
        fallback="generated_card",
    )
    processing_key = f"__system__.{step_id}.card_processing"
    committed_answers = dict(context.get(answers_key, {}) or {})
    latest_answers = dict(committed_answers)
    processing = bool(context.get(processing_key, False))

    def mark_commit(field_key: str) -> None:
        st.session_state[f"{step_id}.card_commit_key"] = field_key

    input_col, preview_col = st.columns(2)

    with input_col:
        for question in ui.get("questions", []):
            field_key = question["key"]
            widget_key = f"{step_id}.question.{field_key}"
            source_key = f"{widget_key}.__source"
            current_value = committed_answers.get(field_key, "")
            sync_editor_state(
                st.session_state,
                editor_key=widget_key,
                source_key=source_key,
                current_text=current_value,
            )
            latest_answers[field_key] = st.text_input(
                question.get("label", field_key),
                key=widget_key,
                placeholder=question.get("placeholder", ""),
                help=question.get("help"),
                disabled=processing,
                on_change=mark_commit,
                args=(field_key,),
            )

    with preview_col:
        with st.container(border=True):
            st.markdown(f"**{ui.get('preview_title', 'Generated card preview')}**")
            if processing:
                st.info(ui.get("loading_preview_text", "Updating preview..."))
            else:
                preview = context.get(card_key, "")
                if preview:
                    st.markdown(preview)
                else:
                    st.info(ui.get("empty_preview_text", "Your card preview will appear here as you answer the questions."))

    if processing:
        try:
            result = _run_step_actions_snapshot(config, context.items(), services, trigger="commit_answer")
            for key, value in result.get("updates", {}).items():
                context.set(key, value)
        finally:
            context.set(processing_key, False)
        st.rerun()
        return None

    question_keys = [question["key"] for question in ui.get("questions", [])]
    all_answered = all(str(latest_answers.get(key, "")).strip() for key in question_keys)

    commit_key = st.session_state.pop(f"{step_id}.card_commit_key", None)
    if commit_key:
        return {
            "event": "commit_answer",
            "updates": {answers_key: latest_answers, processing_key: True},
            "complete": False,
            "defer_after_actions": True,
        }

    if not all_answered:
        st.caption(ui.get("completion_hint", "Answer all questions to finish."))

    if st.button(
        ui.get("button_label", "Continue"),
        key=f"{step_id}.card_builder_continue",
        disabled=not all_answered or processing,
    ):
        return {
            "event": "submit",
            "updates": {answers_key: latest_answers},
            "complete": True,
        }
    return None


def _render_generate(ui: dict, state: dict, context, step_id: str, *, config: dict, services: dict[str, Any]) -> dict[str, Any] | None:
    _render_heading(ui)
    _render_body(ui, context)
    context_entries = ui.get("context_state_keys", [])

    for entry in context_entries:
        if isinstance(entry, dict):
            state_key = entry.get("key")
            title = entry.get("title")
        else:
            state_key = str(entry) if entry else None
            title = None
        if not state_key:
            continue
        value = context.get(state_key, "")
        if value in ("", None, [], {}):
            continue
        with st.container(border=True):
            if title:
                st.markdown(f"**{title}**")
            _render_value(value)

    output_key = pick_state_key(
        state,
        explicit=ui.get("output_key"),
        source="writes",
        suffixes=("generated_rewrite", "generated_text"),
        fallback="generated_text",
    )
    output_value = context.get(output_key, "")
    if output_value:
        with st.container(border=True):
            st.markdown(f"**{ui.get('output_title', 'Generated result')}**")
            _render_value(output_value)
        if st.button(ui.get("continue_button", "Continue"), key=f"{step_id}.continue"):
            return {"event": "submit", "updates": {}, "complete": True}
        return None

    if st.button(ui.get("generate_button", "Generate"), key=f"{step_id}.generate"):
        return {"event": "generate", "updates": {}, "complete": False}
    return None


def _render_heading(ui: dict) -> None:
    if ui.get("hide_title"):
        return
    title = ui.get("title")
    if title:
        st.markdown(f"### {title}")


def _render_body(ui: dict, context) -> None:
    intro = ui.get("intro")
    if intro:
        st.markdown(_interpolate_state(intro, context), unsafe_allow_html=True)
    body = ui.get("body")
    if body:
        st.markdown(_interpolate_state(body, context), unsafe_allow_html=True)


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append_adaptation_history_entry(context, history_key: str, entry: dict[str, Any]) -> None:
    history = list(context.get(history_key, []))
    history.append(entry)
    context.set(history_key, history)


def _update_latest_adaptation_history_entry(context, history_key: str, updates: dict[str, Any]) -> None:
    history = list(context.get(history_key, []))
    if not history:
        return
    history[-1] = dict(history[-1]) | updates
    context.set(history_key, history)


def _render_context_entries(context_entries: list[Any] | None, context) -> None:
    if not context_entries:
        return
    for entry in context_entries:
        if isinstance(entry, dict):
            state_key = entry.get("key")
            title = entry.get("title")
        else:
            state_key = str(entry) if entry else None
            title = None
        if not state_key:
            continue
        value = context.get(state_key, "")
        if value in ("", None, [], {}):
            continue
        with st.container(border=True):
            if title:
                st.markdown(f"**{title}**")
            _render_value(value)


def _render_state_display(ui: dict, state: dict, context, *, explicit: str | None = None, suffixes: tuple[str, ...] = ()) -> None:
    state_key = pick_state_key(state, explicit=explicit, suffixes=suffixes)
    if state_key:
        _render_value(context.get(state_key, ""))


def _render_value(value: Any) -> None:
    if isinstance(value, dict):
        title = value.get("name") or value.get("title")
        body = value.get("description") or value.get("body")
        if title:
            st.markdown(f"**{title}**")
        if body:
            st.markdown(body)
        if not title and not body:
            st.markdown(str(value))
        return
    if value:
        st.markdown(str(value))


def _render_selection_option(option: Any) -> None:
    if isinstance(option, dict):
        _render_value(option)
        return
    st.markdown(str(option))


def _resolve_options(ui: dict, context) -> list[Any]:
    if ui.get("options") is not None:
        return list(ui["options"])
    if "options_state_key" in ui:
        return list(context.get(ui["options_state_key"], []))
    return []


def _interpolate_state(text: str, context) -> str:
    result = text
    for key, value in context.items().items():
        placeholder = f"{{{{{key}}}}}"
        if placeholder in result:
            result = result.replace(placeholder, str(value))
    return result


class _SnapshotContext:
    def __init__(self, values: dict[str, Any]):
        self._values = dict(values)

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._values[key] = value


def _run_step_actions_snapshot(config: dict, values: dict[str, Any], services: dict[str, Any], *, trigger: str) -> dict[str, Any]:
    context = _SnapshotContext(values)
    combined = {"updates": {}, "rerun": False}
    for action in config.get("after_actions", []):
        if action.get("trigger", "submit") != trigger:
            continue
        result = run_action(action, config=config, context=context, services=services)
        updates = result.get("updates", {})
        for key, value in updates.items():
            context.set(key, value)
        combined["updates"] |= updates
        if result.get("rerun"):
            combined["rerun"] = True
        if "step_complete" in result:
            combined["step_complete"] = result["step_complete"]
    return combined
