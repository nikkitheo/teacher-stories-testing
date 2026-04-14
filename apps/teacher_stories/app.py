"""Teacher stories app built on the bot-step infrastructure."""

from __future__ import annotations

from datetime import datetime
import json
import sys
from enum import Enum
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.teacher_stories.step_specs import build_step_specs
from core.flow import current_step, go_to_step, init_flow_state, should_skip_adaptation
from core.session import AppContext
from core.step_runner import run_step
from shared.llm import ensure_openai_key
from shared.storage import get_table


OPINION_STEPS_ENABLED = False
POLICY_SELECTION_ENABLED = False
SHOW_GLOBAL_TITLE = False


class Step(str, Enum):
    CONSENT = "consent"
    PRE_REFLECTION_OPINION = "pre_reflection_opinion"
    STORY_CHAT_1 = "story_chat_1"
    SCENARIO_SELECT_1 = "scenario_select_1"
    SCENARIO_RATING_1 = "scenario_rating_1"
    SCENARIO_ADAPTATION_1 = "scenario_adaptation_1"
    STORY_CHAT_2 = "story_chat_2"
    SCENARIO_RATING_2 = "scenario_rating_2"
    SCENARIO_ADAPTATION_2 = "scenario_adaptation_2"
    POLICY_SELECTION = "policy_selection"
    POST_REFLECTION_OPINION = "post_reflection_opinion"
    COMPLETION = "completion"


def resolve_initial_participant_id() -> str | None:
    participant_id = st.query_params.get("pid")
    if isinstance(participant_id, list):
        participant_id = participant_id[0] if participant_id else None
    if isinstance(participant_id, str):
        participant_id = participant_id.strip() or None
    return participant_id


def step_after_consent(participant_id: str | None) -> Step:
    return Step.PRE_REFLECTION_OPINION if OPINION_STEPS_ENABLED else Step.STORY_CHAT_1


def step_after_flow_2_adaptation() -> Step:
    if POLICY_SELECTION_ENABLED:
        return Step.POLICY_SELECTION
    if OPINION_STEPS_ENABLED:
        return Step.POST_REFLECTION_OPINION
    return Step.COMPLETION


def london_now_iso() -> str:
    return datetime.now(ZoneInfo("Europe/London")).isoformat(timespec="seconds")


def step_after_rating(flow_number: int, rating: int, *, max_allowed_rating: int) -> Step:
    if should_skip_adaptation(rating, max_rating=max_allowed_rating):
        if flow_number == 1:
            return Step.STORY_CHAT_2
        return step_after_flow_2_adaptation()
    if flow_number == 1:
        return Step.SCENARIO_ADAPTATION_1
    return Step.SCENARIO_ADAPTATION_2


def resolve_persona_selection(context: AppContext, *, flow_number: int) -> dict[str, object]:
    selected_index = context.get("flow_1_selected_index")
    scenarios = context.get(f"flow_{flow_number}_generated_scenarios", [])
    if not isinstance(selected_index, int) or not isinstance(scenarios, list) or not scenarios:
        return {
            f"flow_{flow_number}_selected_index": 0,
            f"flow_{flow_number}_selected_scenario": scenarios[0] if scenarios else "",
        }

    bounded_index = min(max(selected_index, 0), len(scenarios) - 1)
    return {
        f"flow_{flow_number}_selected_index": bounded_index,
        f"flow_{flow_number}_selected_scenario": scenarios[bounded_index],
    }


def completion_updates(context: AppContext) -> dict[str, object]:
    combined_transcript = context.get("flow_1_transcript", []) + context.get("flow_2_transcript", [])
    combined_scenarios = context.get("flow_1_generated_scenarios", []) + context.get("flow_2_generated_scenarios", [])
    combined_summary_answers = {
        "ban_beneficiaries": context.get("flow_1_summary_answers"),
        "ban_losers": context.get("flow_2_summary_answers"),
    }
    return {
        "combined_transcript": combined_transcript,
        "combined_scenarios": combined_scenarios,
        "combined_summary_answers": combined_summary_answers,
        "session_package": build_session_package(
            context,
            combined_transcript=combined_transcript,
            combined_scenarios=combined_scenarios,
            combined_summary_answers=combined_summary_answers,
        ),
    }


def build_flow_package(context: AppContext, *, flow_number: int) -> dict[str, object]:
    prefix = f"flow_{flow_number}"
    return {
        "transcript": context.get(f"{prefix}_transcript", []),
        "summary_answers": context.get(f"{prefix}_summary_answers", {}),
        "generated_narratives": context.get(f"{prefix}_generated_scenarios", []),
        "selected_narrative": context.get(f"{prefix}_selected_scenario", ""),
        "selected_index": context.get(f"{prefix}_selected_index"),
        "rating": context.get(f"{prefix}_rating"),
        "adaptation_history": context.get(f"{prefix}_adaptation_history", []),
        "final_narrative": context.get(f"{prefix}_final_scenario", ""),
    }


def build_session_package(
    context: AppContext,
    *,
    combined_transcript: list[object],
    combined_scenarios: list[object],
    combined_summary_answers: dict[str, object],
) -> dict[str, object]:
    completed_at = london_now_iso()
    return {
        "app_id": "teacher_stories",
        "session_id": context.get("session_id", ""),
        "participant_id": context.get("participant_id", ""),
        "consent_given": context.get("consent_given", False),
        "completed_at": completed_at,
        "selected_policy_measures": context.get("selected_policy_measures", []),
        "pre_reflection_opinion": context.get("pre_reflection_opinion"),
        "post_reflection_opinion": context.get("post_reflection_opinion"),
        "flow_1_final_narrative": context.get("flow_1_final_scenario", ""),
        "flow_2_final_narrative": context.get("flow_2_final_scenario", ""),
        "flow_1": build_flow_package(context, flow_number=1),
        "flow_2": build_flow_package(context, flow_number=2),
        "combined": {
            "transcript": combined_transcript,
            "generated_narratives": combined_scenarios,
            "summary_answers": combined_summary_answers,
        },
    }


def init_teacher_page() -> None:
    st.set_page_config(
        page_title="Teacher Stories",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    if SHOW_GLOBAL_TITLE:
        st.title("📚 Teacher Stories")
    st.markdown(
        """
        <style>
        [data-testid="stToolbarActions"] {visibility: hidden;}
        [data-testid="stSidebar"] {
          min-width: 340px;
          max-width: 340px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_missing_pid_screen() -> None:
    st.markdown("#### Teacher Stories Study")
#     st.markdown(
#         """
# Welcome to this placeholder teacher stories flow.

# By continuing, you confirm that you understand this is a research interaction with placeholder content for now.
# """
#     )
    st.error("Please return to the survey and click the link again.")
    # st.button("I consent and want to continue", disabled=True, use_container_width=True)


def render_completion_signal(context: AppContext) -> None:
    participant_id = context.get("participant_id", "")
    components.html(
        f"""
        <script>
          window.top.postMessage({{type: 'mn_complete', pid: {json.dumps(participant_id)}}}, '*');
        </script>
        """,
        height=0,
        width=0,
    )


def init_app_context(context: AppContext) -> None:
    session_ctx = st.runtime.scriptrunner.get_script_run_ctx()
    defaults = {
        "session_id": session_ctx.session_id if session_ctx else "",
        "participant_id": resolve_initial_participant_id(),
        "consent_given": False,
        "pre_reflection_opinion": None,
        "post_reflection_opinion": None,
        "selected_policy_measures": [],
        "combined_transcript": [],
        "combined_scenarios": [],
        "combined_summary_answers": {},
        "session_package": {},
        "saved": False,
    }
    for prefix in ("flow_1", "flow_2"):
        defaults |= {
            f"{prefix}_previous_scenario": None,
            f"{prefix}_transcript": [],
            f"{prefix}_last_user_message": "",
            f"{prefix}_summary_answers": {},
            f"{prefix}_generated_scenarios": [],
            f"{prefix}_selected_index": None,
            f"{prefix}_selected_scenario": "",
            f"{prefix}_rating": None,
            f"{prefix}_final_scenario": "",
            f"{prefix}_adaptation_request": "",
            f"{prefix}_adaptation_history": [],
            f"{prefix}_suggested_scenario": None,
        }
    init_flow_state(context, initial_step=Step.CONSENT, defaults=defaults)


def max_rating() -> int:
    return 10


def main() -> None:
    init_teacher_page()
    ensure_openai_key()

    app_dir = Path(__file__).parent
    step_specs = build_step_specs(app_dir)
    context = AppContext("apps.teacher_stories")
    init_app_context(context)
    services = {"table_write": get_table(st.secrets.get("DYNAMODB_TABLE_NAME_WRITE"))}

    step = current_step(context, Step)
    if not context.get("participant_id"):
        render_missing_pid_screen()
        return

    try:
        result = run_step(step_specs[step.value], context=context, services=services)
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

    if result.get("rerun"):
        st.rerun()

    if result["status"] != "completed":
        if step == Step.COMPLETION:
            render_completion_signal(context)
        return

    if step == Step.CONSENT:
        go_to_step(context, step_after_consent(context.get("participant_id")), {"consent_given": True})

    elif step == Step.PRE_REFLECTION_OPINION:
        go_to_step(context, Step.STORY_CHAT_1)

    elif step == Step.STORY_CHAT_1:
        go_to_step(context, Step.SCENARIO_SELECT_1)

    elif step == Step.SCENARIO_SELECT_1:
        go_to_step(context, Step.SCENARIO_RATING_1, {"flow_1_final_scenario": context.get("flow_1_selected_scenario")})

    elif step == Step.SCENARIO_RATING_1:
        go_to_step(
            context,
            step_after_rating(1, context.get("flow_1_rating"), max_allowed_rating=max_rating()),
            {"flow_1_final_scenario": context.get("flow_1_selected_scenario")},
        )

    elif step == Step.SCENARIO_ADAPTATION_1:
        go_to_step(context, Step.STORY_CHAT_2)

    elif step == Step.STORY_CHAT_2:
        selection = resolve_persona_selection(context, flow_number=2)
        go_to_step(
            context,
            Step.SCENARIO_RATING_2,
            selection | {"flow_2_final_scenario": selection["flow_2_selected_scenario"]},
        )

    elif step == Step.SCENARIO_RATING_2:
        next_step = step_after_rating(2, context.get("flow_2_rating"), max_allowed_rating=max_rating())
        updates = {"flow_2_final_scenario": context.get("flow_2_selected_scenario")}
        if next_step == Step.COMPLETION:
            updates |= completion_updates(context)
        go_to_step(context, next_step, updates)

    elif step == Step.SCENARIO_ADAPTATION_2:
        next_step = step_after_flow_2_adaptation()
        updates = completion_updates(context) if next_step == Step.COMPLETION else {}
        go_to_step(context, next_step, updates)

    elif step == Step.POLICY_SELECTION:
        next_step = Step.POST_REFLECTION_OPINION if OPINION_STEPS_ENABLED else Step.COMPLETION
        updates = {} if OPINION_STEPS_ENABLED else completion_updates(context)
        go_to_step(context, next_step, updates)

    elif step == Step.POST_REFLECTION_OPINION:
        go_to_step(context, Step.COMPLETION, completion_updates(context))


if __name__ == "__main__":
    main()
