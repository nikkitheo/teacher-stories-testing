"""Prompt builders shared by backend modules."""

from __future__ import annotations

from langchain_core.prompts import PromptTemplate


STORY_PLACEHOLDER = "STORY-HERE"


def build_questions_prompt(collection_config: dict) -> PromptTemplate:
    questions_list = "".join(
        f"{index + 1}. {question}\n" for index, question in enumerate(collection_config["questions"])
    )
    collection_complete = (
        "Once you have collected an answer to the question"
        if len(collection_config["questions"]) == 1
        else f"Once you have collected answers to all {len(collection_config['questions'])} questions"
    )
    template = (
        "{persona}\n\n"
        "Your goal is to gather structured answers to the following questions:\n\n"
        "{questions}\n"
        "Ask each question one at a time.\n"
        "{language_type}\n"
        "Ensure you get at least a basic answer to each question before moving to the next.\n"
        "Never answer for the human. If you unsure what the human meant, ask again. "
        "{topic_restriction}\n"
        "{collection_complete}, stop the conversation and write a single word \"FINISHED\".\n\n"
        "Current conversation:\n"
        "{history}\n"
        "Human: {input}\n"
        "AI: "
    )
    return PromptTemplate(
        template=template,
        input_variables=["history", "input"],
        partial_variables={
            "persona": collection_config["persona"],
            "questions": questions_list,
            "language_type": collection_config.get("language_type", ""),
            "topic_restriction": collection_config.get("topic_restriction", ""),
            "collection_complete": collection_complete,
        },
    )


def build_extraction_prompt(summary_questions: dict) -> PromptTemplate:
    keys = [f"`{key}`" for key in summary_questions.keys()]
    keys_text = ", ".join(keys[:-1]) + f", and {keys[-1]}" if len(keys) > 1 else keys[0]
    question_count_suffix = "s" if len(summary_questions) else ""
    question_lines = (
        f"These correspond to the following question{question_count_suffix}:\n"
        + "".join(f"{index + 1}: {question}\n" for index, question in enumerate(summary_questions.values()))
    )
    template = (
        "You are an expert extraction algorithm. "
        "Only extract relevant information from the Human answers in the text. "
        "Use only the words and phrases that the text contains. "
        "If you do not know the value of an attribute asked to extract, return "
        "null for the attribute's value.\n\n"
        "You will output a JSON with {keys_text} keys.\n\n"
        "{question_lines}"
        "Message to date: {conversation_history}\n\n"
        "Remember, only extract text that is in the messages above and do not change it. "
    )
    return PromptTemplate(
        template=template,
        input_variables=["conversation_history"],
        partial_variables={"keys_text": keys_text, "question_lines": question_lines},
    )


def build_scenario_prompt(summary_questions: dict, example_config: dict) -> PromptTemplate:
    q_and_a = "".join(
        f"Question: {question}\nAnswer: {{{key}}}\n" for key, question in summary_questions.items()
    )
    example = (
        "Example:\n"
        f"{example_config['conversation'].strip()}\n\n"
        "The scenario based on these responses:\n"
        f"\"{example_config['scenario'].strip()}\""
    )
    template = (
        "{persona}\n\n"
        "{example}\n\n"
        "Your task:\nCreate a scenario based on the following answers:\n\n"
        f"{q_and_a}\n"
        "Create a scenario based on these responses.\n\n"
        "Your output should be a JSON file with a single entry called \"output_scenario\"."
    )
    return PromptTemplate(
        template=template,
        input_variables=["persona"] + list(summary_questions.keys()),
        partial_variables={"example": example},
    )


def build_single_narrative_prompt(summary_questions: dict, example_config: dict) -> PromptTemplate:
    q_and_a = "".join(
        f"Question: {question}\nAnswer: {{{key}}}\n" for key, question in summary_questions.items()
    )
    example = (
        "Example:\n"
        f"{example_config['conversation'].strip()}\n\n"
        "The narrative based on these responses:\n"
        f"\"{example_config['scenario'].strip()}\""
    )
    template = (
        "{persona}\n\n"
        "{example}\n\n"
        "Your task:\nCreate a single narrative based on the following answers:\n\n"
        f"{q_and_a}\n"
        "Return a JSON object with a single key called \"output_narrative\"."
    )
    return PromptTemplate(
        template=template,
        input_variables=["persona"] + list(summary_questions.keys()),
        partial_variables={"example": example},
    )


def build_adaptation_prompt(prompt_text: str) -> PromptTemplate:
    return PromptTemplate.from_template(prompt_text)


def build_structured_adaptation_prompt(adaptation_config: dict) -> PromptTemplate:
    guidance = adaptation_config.get("guidance", "Keep the voice and core meaning stable while making the requested change.")
    example_block = ""
    example = adaptation_config.get("example")
    if example:
        example_block = (
            "\nExample:\n"
            f"Original narrative: {example.get('scenario', '').strip()}\n"
            f"Requested change: {example.get('request', '').strip()}\n"
            f"Updated narrative: {example.get('output', '').strip()}\n"
        )
    template = (
        "{persona}\n\n"
        "You are helping revise an existing first-person narrative.\n\n"
        "Original narrative:\n{scenario}\n\n"
        "Requested change:\n{input}\n\n"
        "{guidance}\n"
        "{example_block}\n"
        'Return a JSON object with a single key called "new_scenario".'
    )
    return PromptTemplate(
        template=template,
        input_variables=["scenario", "input"],
        partial_variables={
            "persona": adaptation_config["persona"],
            "guidance": guidance,
            "example_block": example_block,
        },
    )


def build_contextual_rewrite_prompt(rewrite_config: dict) -> PromptTemplate:
    guidance = rewrite_config.get(
        "guidance",
        "Keep the situation recognizable while shifting the stance, interpretation, and response through the selected lens.",
    )
    example_block = ""
    example = rewrite_config.get("example")
    if example:
        example_block = (
            "\nExample:\n"
            f"Original narrative: {example.get('narrative', '').strip()}\n"
            f"Selected context: {example.get('context', '').strip()}\n"
            f"Rewritten narrative: {example.get('output', '').strip()}\n"
        )
    template = (
        "{persona}\n\n"
        "Original narrative:\n{narrative}\n\n"
        "Selected context:\n{context}\n\n"
        "{guidance}\n"
        "{example_block}\n"
        'Return a JSON object with a single key called "rewritten_narrative".'
    )
    return PromptTemplate(
        template=template,
        input_variables=["narrative", "context"],
        partial_variables={
            "persona": rewrite_config["persona"],
            "guidance": guidance,
            "example_block": example_block,
        },
    )


def build_card_generation_prompt(card_config: dict) -> PromptTemplate:
    guidance = card_config.get(
        "guidance",
        "Create a compact card in markdown with a short title, a one-paragraph identity description, and a short list of 2-4 actions or reminders.",
    )
    answers_label = card_config.get("answers_label", "Questionnaire answers")
    example_block = ""
    example = card_config.get("example")
    if example:
        example_block = (
            "\nExample:\n"
            f"Selected context: {example.get('context', '').strip()}\n"
            f"Answers: {example.get('answers', '').strip()}\n"
            f"Card output:\n{example.get('output', '').strip()}\n"
        )
    template = (
        "{persona}\n\n"
        "Selected context:\n{context}\n"
        "{answers_label}:\n{answers}\n\n"
        "{guidance}\n"
        "{example_block}\n"
        'Return a JSON object with a single key called "card_text".'
    )
    return PromptTemplate(
        template=template,
        input_variables=["context", "answers"],
        partial_variables={
            "persona": card_config["persona"],
            "guidance": guidance,
            "example_block": example_block,
            "answers_label": answers_label,
        },
    )
