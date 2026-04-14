"""Action registry for bot-step runtime."""

from __future__ import annotations

import datetime
import html
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from langchain.output_parsers.json import SimpleJsonOutputParser
from langchain_core.output_parsers import StrOutputParser

from core.state_keys import pick_state_key
from shared.llm import get_chat_model
from shared.prompt_builders import (
    STORY_PLACEHOLDER,
    build_adaptation_prompt,
    build_extraction_prompt,
    build_questions_prompt,
    build_single_narrative_prompt,
    build_scenario_prompt,
    build_card_generation_prompt,
    build_contextual_rewrite_prompt,
    build_structured_adaptation_prompt,
)
from shared.storage import fetch_latest_by_participant, save_item


def run_action(action: dict, *, config: dict, context, services: dict[str, Any]) -> dict[str, Any]:
    """Run one named action against the current step config and shared state."""
    if action.get("enabled", True) is False:
        return {"updates": {}}
    name = action["name"]
    handler = ACTIONS[name]
    return handler(action, config=config, context=context, services=services)


def _get_json_chat_model(model_name: str, *, temperature: float) -> Any:
    return get_chat_model(model_name, temperature=temperature).bind(response_format={"type": "json_object"})


def _load_previous_scenario(action: dict, *, config: dict, context, services: dict[str, Any]) -> dict[str, Any]:
    state = config.get("state", {})
    participant_id_key = pick_state_key(
        state,
        explicit=action.get("participant_id_key"),
        suffixes=("participant_id",),
        exact="participant_id",
        fallback="participant_id",
    )
    output_key = pick_state_key(
        state,
        explicit=action.get("output_key"),
        suffixes=("previous_scenario",),
        exact="previous_scenario",
        fallback="previous_scenario",
    )
    participant_id = context.get(participant_id_key, "")
    table = services.get(action.get("table_service", "table_read"))
    previous_scenario = fetch_latest_by_participant(table, participant_id)
    if action.get("required", False) and not previous_scenario:
        raise RuntimeError(
            "This study requires your previous scenario, but we couldn't find one associated with your participant ID."
        )
    return {"updates": {output_key: previous_scenario}}


def _initialize_chat(action: dict, *, config: dict, context, services: dict[str, Any]) -> dict[str, Any]:
    state = config.get("state", {})
    transcript_key = pick_state_key(
        state,
        explicit=action.get("transcript_key"),
        suffixes=("transcript",),
        exact="transcript",
        fallback="transcript",
    )
    previous_key = pick_state_key(
        state,
        explicit=action.get("previous_scenario_key"),
        suffixes=("previous_scenario",),
        exact="previous_scenario",
        fallback="previous_scenario",
    )
    if context.get(transcript_key):
        return {"updates": {}}
    bot = config["bot"]
    intro = bot.get("intro", "").strip()
    previous_scenario = context.get(previous_key)
    if STORY_PLACEHOLDER in intro and previous_scenario:
        escaped = html.escape(str(previous_scenario)).replace("\n", "<br>")
        intro = intro.replace(STORY_PLACEHOLDER, f'<span style="color: orange; font-weight: 600;">{escaped}</span>')
    elif STORY_PLACEHOLDER in intro:
        intro = intro.replace(STORY_PLACEHOLDER, "")
    return {"updates": {transcript_key: [{"role": "assistant", "content": intro}]}}


def _conversation_turn(action: dict, *, config: dict, context, services: dict[str, Any]) -> dict[str, Any]:
    state = config.get("state", {})
    step_id = config["step"]["id"]
    post_chat_enabled = bool(config.get("ui", {}).get("post_chat"))
    transcript_key = pick_state_key(
        state,
        explicit=action.get("transcript_key"),
        suffixes=("transcript",),
        exact="transcript",
        fallback="transcript",
    )
    response_key = pick_state_key(
        state,
        explicit=action.get("response_key"),
        source="writes",
        suffixes=("last_user_message",),
        exact="last_user_message",
        fallback="last_user_message",
    )
    transcript = list(context.get(transcript_key, []))
    user_message = context.get(response_key, "")
    if not user_message:
        return {"updates": {}}
    prompt = build_questions_prompt(config["bot"])
    model = get_chat_model(config.get("model", "gpt-4o"), temperature=0.3)
    chain = prompt | model | StrOutputParser()
    history_lines = []
    for item in transcript:
        role = "AI" if item["role"] == "assistant" else "Human"
        history_lines.append(f"{role}: {item['content']}")
    response = chain.invoke({"history": "\n".join(history_lines), "input": user_message})
    finished = "FINISHED" in response
    transcript.append({"role": "user", "content": user_message})
    updates = {
        transcript_key: transcript,
        response_key: "",
        f"__system__.{step_id}.chat_pending": False,
    }
    if not finished:
        transcript.append({"role": "assistant", "content": response})
        updates[transcript_key] = transcript
        return {"updates": updates, "rerun": True, "step_complete": False}
    if post_chat_enabled:
        updates |= {
            f"__system__.{step_id}.chat_finished": True,
            f"__system__.{step_id}.post_chat_processing": False,
            f"__system__.{step_id}.post_chat_ready": False,
        }
        return {"updates": updates, "rerun": True, "step_complete": False}
    return {"updates": updates, "step_complete": True}


def _stringify_transcript(transcript: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in transcript:
        role = item.get("role")
        content = item.get("content", "")
        if role == "assistant":
            lines.append(f"AI: {content}")
        elif role == "user":
            lines.append(f"Human: {content}")
        else:
            lines.append(str(content))
    return "\n".join(lines)


def _stringify_extraction_input(transcript: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    pending_question: str | None = None

    for item in transcript:
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if not content:
            continue

        if role == "assistant":
            if "?" in content:
                pending_question = content
            continue

        if role != "user":
            continue

        if pending_question:
            blocks.append(f"Question: {pending_question}\nHuman: {content}")
            pending_question = None
        else:
            blocks.append(f"Human: {content}")

    return "\n\n".join(blocks)


def _normalize_summary_answers(summary_config: dict, result: dict[str, Any]) -> dict[str, str]:
    summary_answers: dict[str, str] = {}
    for key in summary_config["questions"].keys():
        value = result.get(key, "")
        if value is None or (isinstance(value, str) and value.strip().lower() == "null"):
            summary_answers[key] = ""
        else:
            summary_answers[key] = str(value).strip()
    return summary_answers


def _summarize_conversation(action: dict, *, config: dict, context, services: dict[str, Any]) -> dict[str, Any]:
    state = config.get("state", {})
    summary_config = config["summary"]
    prompt = build_extraction_prompt(summary_config["questions"])
    model = _get_json_chat_model(summary_config.get("model", config.get("model", "gpt-4o")), temperature=0.1)
    chain = prompt | model | SimpleJsonOutputParser()
    transcript_key = pick_state_key(
        state,
        explicit=action.get("transcript_key"),
        suffixes=("transcript",),
        exact="transcript",
        fallback="transcript",
    )
    output_key = pick_state_key(
        state,
        explicit=action.get("output_key"),
        suffixes=("summary_answers",),
        exact="summary_answers",
        fallback="summary_answers",
    )
    transcript = context.get(transcript_key, [])
    conversation_history = _stringify_extraction_input(transcript)
    result = chain.invoke({"conversation_history": conversation_history})
    summary_answers = _normalize_summary_answers(summary_config, result)
    return {"updates": {output_key: summary_answers}}


def _get_story_questions(config: dict) -> dict:
    summary = config.get("summary", {})
    questions = summary.get("questions")
    if not questions:
        raise KeyError("Story generation requires summary.questions to be configured.")
    return questions


def _get_generation_personas(generation: dict) -> list[str]:
    personas_config = generation.get("personas")
    if not isinstance(personas_config, dict) or not personas_config:
        raise KeyError('Story generation requires [generation.personas] with 1 to 3 entries.')
    personas = [str(persona).strip() for persona in personas_config.values() if str(persona).strip()]
    if not personas:
        raise ValueError("Story generation personas cannot be empty.")
    if len(personas) > 3:
        raise ValueError("Story generation supports at most 3 personas.")
    return personas


def _generate_scenarios(action: dict, *, config: dict, context, services: dict[str, Any]) -> dict[str, Any]:
    state = config.get("state", {})
    generation = config["generation"]
    prompt = build_scenario_prompt(_get_story_questions(config), generation["example"])
    model = _get_json_chat_model(generation.get("model", config.get("model", "gpt-4o")), temperature=0.3)
    chain = prompt | model | SimpleJsonOutputParser()
    summary_key = pick_state_key(
        state,
        explicit=action.get("summary_key"),
        suffixes=("summary_answers",),
        exact="summary_answers",
        fallback="summary_answers",
    )
    output_key = pick_state_key(
        state,
        explicit=action.get("output_key"),
        suffixes=("generated_scenarios",),
        exact="generated_scenarios",
        fallback="generated_scenarios",
    )
    summary_answers = context.get(summary_key, {})
    personas = _get_generation_personas(generation)

    def generate(persona: str) -> str:
        result = chain.invoke({"persona": persona} | summary_answers)
        if not isinstance(result, dict) or "output_scenario" not in result:
            raise ValueError("Scenario generator returned an unexpected payload")
        return result["output_scenario"]

    scenarios = [None] * len(personas)
    with ThreadPoolExecutor(max_workers=min(3, len(personas) or 1)) as executor:
        future_map = {executor.submit(generate, persona): index for index, persona in enumerate(personas)}
        for future in as_completed(future_map):
            scenarios[future_map[future]] = future.result()
    return {"updates": {output_key: scenarios}}


def _generate_single_narrative(action: dict, *, config: dict, context, services: dict[str, Any]) -> dict[str, Any]:
    state = config.get("state", {})
    generation = config["generation"]
    prompt = build_single_narrative_prompt(_get_story_questions(config), generation["example"])
    model = _get_json_chat_model(generation.get("model", config.get("model", "gpt-4o")), temperature=0.3)
    chain = prompt | model | SimpleJsonOutputParser()
    summary_key = pick_state_key(
        state,
        explicit=action.get("summary_key"),
        suffixes=("summary_answers",),
        exact="summary_answers",
        fallback="summary_answers",
    )
    output_key = pick_state_key(
        state,
        explicit=action.get("output_key"),
        suffixes=("generated_narratives", "generated_scenarios", "generated_options"),
        exact="generated_narratives",
        fallback="generated_narratives",
    )
    summary_answers = context.get(summary_key, {})
    personas = _get_generation_personas(generation)

    def generate(persona: str) -> str:
        result = chain.invoke({"persona": persona} | summary_answers)
        if not isinstance(result, dict) or "output_narrative" not in result:
            raise ValueError("Narrative generator returned an unexpected payload")
        return result["output_narrative"]

    narratives = [None] * len(personas)
    with ThreadPoolExecutor(max_workers=min(3, len(personas) or 1)) as executor:
        future_map = {executor.submit(generate, persona): index for index, persona in enumerate(personas)}
        for future in as_completed(future_map):
            narratives[future_map[future]] = future.result()
    return {"updates": {output_key: narratives}}


def _generate_adaptation(action: dict, *, config: dict, context, services: dict[str, Any]) -> dict[str, Any]:
    state = config.get("state", {})
    adaptation = config["adaptation"]
    prompt = (
        build_adaptation_prompt(adaptation["prompt"])
        if "prompt" in adaptation
        else build_structured_adaptation_prompt(adaptation)
    )
    model = _get_json_chat_model(adaptation.get("model", config.get("model", "gpt-4o")), temperature=0.3)
    chain = prompt | model | SimpleJsonOutputParser()
    scenario_key = pick_state_key(
        state,
        explicit=action.get("scenario_key"),
        suffixes=("final_scenario",),
        exact="final_scenario",
        fallback="final_scenario",
    )
    request_key = pick_state_key(
        state,
        explicit=action.get("request_key"),
        source="writes",
        suffixes=("adaptation_request",),
        exact="adaptation_request",
        fallback="adaptation_request",
    )
    output_key = pick_state_key(
        state,
        explicit=action.get("output_key"),
        suffixes=("suggested_scenario",),
        exact="suggested_scenario",
        fallback="suggested_scenario",
    )
    scenario = context.get(scenario_key, "")
    user_request = context.get(request_key, "")
    result = chain.invoke({"scenario": scenario, "input": user_request})
    if not isinstance(result, dict) or "new_scenario" not in result:
        raise ValueError("Adaptation generator returned an unexpected payload")
    return {"updates": {output_key: result["new_scenario"]}, "rerun": True, "step_complete": False}


def _generate_contextual_rewrite(action: dict, *, config: dict, context, services: dict[str, Any]) -> dict[str, Any]:
    state = config.get("state", {})
    rewrite = config["rewrite"]
    prompt = build_adaptation_prompt(rewrite["prompt"]) if "prompt" in rewrite else build_contextual_rewrite_prompt(rewrite)
    model = _get_json_chat_model(rewrite.get("model", config.get("model", "gpt-4o")), temperature=0.3)
    chain = prompt | model | SimpleJsonOutputParser()
    narrative_key = pick_state_key(
        state,
        explicit=action.get("narrative_key"),
        suffixes=("final_narrative_1", "final_scenario"),
        fallback="final_narrative_1",
    )
    context_key = pick_state_key(
        state,
        explicit=action.get("context_key") or action.get("hero_key"),
        suffixes=("selected_context_text", "selected_context"),
        fallback="selected_context",
    )
    output_key = pick_state_key(
        state,
        explicit=action.get("output_key"),
        suffixes=("generated_rewrite",),
        fallback="generated_rewrite",
    )
    context_value = context.get(context_key, "")
    result = chain.invoke(
        {
            "narrative": context.get(narrative_key, ""),
            "context": str(context_value or ""),
        }
    )
    if not isinstance(result, dict) or "rewritten_narrative" not in result:
        raise ValueError("Contextual rewrite returned an unexpected payload")
    return {"updates": {output_key: result["rewritten_narrative"]}, "rerun": True, "step_complete": False}


def _generate_card(action: dict, *, config: dict, context, services: dict[str, Any]) -> dict[str, Any]:
    state = config.get("state", {})
    card_generation = config["card_generation"]
    prompt = build_adaptation_prompt(card_generation["prompt"]) if "prompt" in card_generation else build_card_generation_prompt(card_generation)
    model = _get_json_chat_model(card_generation.get("model", config.get("model", "gpt-4o")), temperature=0.3)
    chain = prompt | model | SimpleJsonOutputParser()
    answers_key = pick_state_key(
        state,
        explicit=action.get("answers_key"),
        suffixes=("card_answers",),
        exact="card_answers",
        fallback="card_answers",
    )
    context_key = pick_state_key(
        state,
        explicit=action.get("context_key") or action.get("hero_key"),
        suffixes=("selected_context",),
        fallback="selected_context",
    )
    output_key = pick_state_key(
        state,
        explicit=action.get("output_key"),
        suffixes=("generated_card",),
        fallback="generated_card",
    )
    context_value = context.get(context_key, "")
    answers = context.get(answers_key, {}) or {}
    ordered_answers_blocks: list[str] = []
    for question in config.get("ui", {}).get("questions", []):
        answer = str(answers.get(question["key"], "")).strip()
        if not answer:
            continue
        prompt = question.get("label", question["key"])
        ordered_answers_blocks.append(f"Question: {prompt}\nAnswer: {answer}")
    ordered_answers = "\n\n".join(ordered_answers_blocks)
    result = chain.invoke(
        {
            "context": str(context_value or ""),
            "answers": ordered_answers,
        }
    )
    if not isinstance(result, dict) or "card_text" not in result:
        raise ValueError("Card generator returned an unexpected payload")
    return {"updates": {output_key: result["card_text"]}, "rerun": True, "step_complete": False}


def _package_session(action: dict, *, config: dict, context, services: dict[str, Any]) -> dict[str, Any]:
    session_data = {
        "session_id": context.get("session_id", ""),
        "participant_id": context.get("participant_id", ""),
        "completion_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "final_scenario": context.get(action.get("final_scenario_key", "final_scenario"), ""),
    }
    for field in action.get("copy_fields", []):
        if context.get(field) is not None:
            session_data[field] = context.get(field)
    if action.get("scenarios_key") and context.get(action["scenarios_key"]) is not None:
        session_data["scenarios"] = [{"text": item} for item in context.get(action["scenarios_key"], [])]
    if action.get("transcript_key") and context.get(action["transcript_key"]) is not None:
        transcript = context.get(action["transcript_key"], [])
        session_data["chat_history"] = transcript
        session_data["chat_history_single_string"] = str(transcript)
    return {"updates": {action.get("output_key", "session_package"): session_data}}


def _save_session(action: dict, *, config: dict, context, services: dict[str, Any]) -> dict[str, Any]:
    if not action.get("enabled", True):
        return {"updates": {action.get("saved_key", "saved"): False}}
    table = services.get(action.get("table_service", "table_write"))
    package = context.get(action.get("package_key", "session_package"), {})
    saved = save_item(table, package)
    return {"updates": {action.get("saved_key", "saved"): saved}}


ACTIONS = {
    "load_previous_scenario": _load_previous_scenario,
    "initialize_chat": _initialize_chat,
    "conversation_turn": _conversation_turn,
    "summarize_conversation": _summarize_conversation,
    "generate_scenarios": _generate_scenarios,
    "generate_single_narrative": _generate_single_narrative,
    "generate_adaptation": _generate_adaptation,
    "generate_contextual_rewrite": _generate_contextual_rewrite,
    "generate_card": _generate_card,
    "package_session": _package_session,
    "save_session": _save_session,
}
