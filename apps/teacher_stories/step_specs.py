"""Code-defined step specs for the teacher stories app."""

from __future__ import annotations

from pathlib import Path

from core.step_specs import ActionSpec, accept_step, chat_step, edit_step, multi_field_form_step, rating_step, selection_step


def build_step_specs(app_dir: Path) -> dict[str, object]:
    steps_dir = app_dir / "steps"
    return {
        "consent": accept_step(
            "consent",
            steps_dir / "consent.toml",
            response_key="consent_given",
            writes=("consent_given",),
        ),
        "pre_reflection_opinion": multi_field_form_step(
            "pre_reflection_opinion",
            steps_dir / "pre_reflection_opinion.toml",
            reads=("pre_reflection_opinion",),
            writes=("pre_reflection_opinion",),
        ),
        "story_chat_1": chat_step(
            "story_chat_1",
            steps_dir / "story_chat_1.toml",
            transcript_key="flow_1_transcript",
            response_key="flow_1_last_user_message",
            reads=("flow_1_previous_scenario", "flow_1_transcript", "flow_1_last_user_message", "flow_1_summary_answers", "flow_1_generated_scenarios"),
            writes=("flow_1_previous_scenario", "flow_1_transcript", "flow_1_last_user_message", "flow_1_summary_answers", "flow_1_generated_scenarios"),
            model="gpt-4o",
            before_actions=(
                ActionSpec(
                    "initialize_chat",
                    params={"transcript_key": "flow_1_transcript", "previous_scenario_key": "flow_1_previous_scenario"},
                ),
            ),
            after_actions=(
                ActionSpec(
                    "conversation_turn",
                    trigger="submit",
                    params={"transcript_key": "flow_1_transcript", "response_key": "flow_1_last_user_message"},
                ),
                ActionSpec(
                    "summarize_conversation",
                    trigger="post_chat_process",
                    params={"transcript_key": "flow_1_transcript", "output_key": "flow_1_summary_answers"},
                ),
                ActionSpec(
                    "generate_scenarios",
                    trigger="post_chat_process",
                    params={"summary_key": "flow_1_summary_answers", "output_key": "flow_1_generated_scenarios"},
                ),
            ),
        ),
        "scenario_select_1": selection_step(
            "scenario_select_1",
            steps_dir / "scenario_select_1.toml",
            options_key="flow_1_generated_scenarios",
            selected_index_key="flow_1_selected_index",
            response_key="flow_1_selected_scenario",
            reads=("flow_1_transcript", "flow_1_summary_answers", "flow_1_generated_scenarios", "flow_1_selected_index", "flow_1_selected_scenario"),
            writes=("flow_1_transcript", "flow_1_summary_answers", "flow_1_generated_scenarios", "flow_1_selected_index", "flow_1_selected_scenario"),
        ),
        "scenario_rating_1": rating_step(
            "scenario_rating_1",
            steps_dir / "scenario_rating_1.toml",
            display_state_key="flow_1_selected_scenario",
            response_key="flow_1_rating",
            reads=("flow_1_selected_scenario", "flow_1_rating"),
            writes=("flow_1_selected_scenario", "flow_1_rating"),
        ),
        "scenario_adaptation_1": edit_step(
            "scenario_adaptation_1",
            steps_dir / "scenario_adaptation_1.toml",
            current_key="flow_1_final_scenario",
            original_key="flow_1_selected_scenario",
            suggestion_key="flow_1_suggested_scenario",
            request_key="flow_1_adaptation_request",
            history_key="flow_1_adaptation_history",
            reads=("flow_1_selected_scenario", "flow_1_final_scenario", "flow_1_adaptation_request", "flow_1_suggested_scenario", "flow_1_adaptation_history"),
            writes=("flow_1_selected_scenario", "flow_1_final_scenario", "flow_1_adaptation_request", "flow_1_suggested_scenario", "flow_1_adaptation_history"),
            model="gpt-4o",
            after_actions=(
                ActionSpec(
                    "generate_adaptation",
                    trigger="request_adaptation",
                    params={
                        "scenario_key": "flow_1_final_scenario",
                        "request_key": "flow_1_adaptation_request",
                        "output_key": "flow_1_suggested_scenario",
                    },
                ),
            ),
        ),
        "story_chat_2": chat_step(
            "story_chat_2",
            steps_dir / "story_chat_2.toml",
            transcript_key="flow_2_transcript",
            response_key="flow_2_last_user_message",
            reads=("flow_2_previous_scenario", "flow_2_transcript", "flow_2_last_user_message", "flow_2_summary_answers", "flow_2_generated_scenarios"),
            writes=("flow_2_previous_scenario", "flow_2_transcript", "flow_2_last_user_message", "flow_2_summary_answers", "flow_2_generated_scenarios"),
            model="gpt-4o",
            before_actions=(
                ActionSpec(
                    "initialize_chat",
                    params={"transcript_key": "flow_2_transcript", "previous_scenario_key": "flow_2_previous_scenario"},
                ),
            ),
            after_actions=(
                ActionSpec(
                    "conversation_turn",
                    trigger="submit",
                    params={"transcript_key": "flow_2_transcript", "response_key": "flow_2_last_user_message"},
                ),
                ActionSpec(
                    "summarize_conversation",
                    trigger="post_chat_process",
                    params={"transcript_key": "flow_2_transcript", "output_key": "flow_2_summary_answers"},
                ),
                ActionSpec(
                    "generate_scenarios",
                    trigger="post_chat_process",
                    params={"summary_key": "flow_2_summary_answers", "output_key": "flow_2_generated_scenarios"},
                ),
            ),
        ),
        "scenario_rating_2": rating_step(
            "scenario_rating_2",
            steps_dir / "scenario_rating_2.toml",
            display_state_key="flow_2_selected_scenario",
            response_key="flow_2_rating",
            reads=("flow_2_selected_scenario", "flow_2_rating"),
            writes=("flow_2_selected_scenario", "flow_2_rating"),
        ),
        "scenario_adaptation_2": edit_step(
            "scenario_adaptation_2",
            steps_dir / "scenario_adaptation_2.toml",
            current_key="flow_2_final_scenario",
            original_key="flow_2_selected_scenario",
            suggestion_key="flow_2_suggested_scenario",
            request_key="flow_2_adaptation_request",
            history_key="flow_2_adaptation_history",
            reads=("flow_2_selected_scenario", "flow_2_final_scenario", "flow_2_adaptation_request", "flow_2_suggested_scenario", "flow_2_adaptation_history"),
            writes=("flow_2_selected_scenario", "flow_2_final_scenario", "flow_2_adaptation_request", "flow_2_suggested_scenario", "flow_2_adaptation_history"),
            model="gpt-4o",
            after_actions=(
                ActionSpec(
                    "generate_adaptation",
                    trigger="request_adaptation",
                    params={
                        "scenario_key": "flow_2_final_scenario",
                        "request_key": "flow_2_adaptation_request",
                        "output_key": "flow_2_suggested_scenario",
                    },
                ),
            ),
        ),
        "policy_selection": multi_field_form_step(
            "policy_selection",
            steps_dir / "policy_selection.toml",
            reads=("flow_1_final_scenario", "flow_2_final_scenario", "selected_policy_measures"),
            writes=("selected_policy_measures",),
        ),
        "post_reflection_opinion": multi_field_form_step(
            "post_reflection_opinion",
            steps_dir / "post_reflection_opinion.toml",
            reads=("post_reflection_opinion", "flow_1_final_scenario", "flow_2_final_scenario"),
            writes=("post_reflection_opinion",),
        ),
        "completion": accept_step(
            "completion",
            steps_dir / "completion.toml",
            reads=("session_id", "participant_id", "flow_1_final_scenario", "flow_2_final_scenario", "flow_1_rating", "flow_2_rating", "selected_policy_measures", "pre_reflection_opinion", "post_reflection_opinion", "combined_summary_answers", "combined_scenarios", "combined_transcript", "session_package", "saved"),
            writes=("session_id", "participant_id", "flow_1_final_scenario", "flow_2_final_scenario", "flow_1_rating", "flow_2_rating", "selected_policy_measures", "pre_reflection_opinion", "post_reflection_opinion", "combined_summary_answers", "combined_scenarios", "combined_transcript", "session_package", "saved"),
            ui={
                "context_state_keys": [
                    {"key": "flow_1_final_scenario", "title": "Narrative 1 — Pupils who would benefit from a ban"},
                    {"key": "flow_2_final_scenario", "title": "Narrative 2 — Pupils who would lose out from a ban"},
                ],
            },
            before_actions=(
                ActionSpec(
                    "save_session",
                    params={
                        "enabled": True,
                        "package_key": "session_package",
                        "saved_key": "saved",
                        "table_service": "table_write",
                    },
                ),
            ),
        ),
    }
