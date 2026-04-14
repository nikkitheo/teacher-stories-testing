# Infrastructure V2 Technical Reference

`infrastructure_v2` is a Streamlit-based framework for building small guided apps that combine:

- page/step flows
- structured session state
- reusable UI step types
- reusable LLM-backed actions
- app-specific content in TOML
- app-specific wiring in Python

The main design goal is to keep new apps easy to set up without hiding all behavior inside one monolithic app file.

## Core Idea

Each app is built from **steps**.

Each step has:

- a `mode`
- a TOML content file
- declared state reads/writes
- optional `before_actions`
- optional `after_actions`

The split is intentional:

- **TOML** owns page copy and prompt/config content
- **Python step specs** own state contracts and action wiring
- **shared infrastructure** owns rendering, runtime, and reusable actions

This means a new app usually comes from:

1. defining session state defaults in `app.py`
2. defining the flow transitions in `app.py`
3. defining step specs in `step_specs.py`
4. writing step content TOMLs in `steps/`

## Repository Structure

- [`apps`](/Users/k20037673/Desktop/test claude/infrastructure_v2/apps): concrete apps built on the framework
- [`core`](/Users/k20037673/Desktop/test claude/infrastructure_v2/core): runtime, renderers, state helpers, config loading, flow helpers
- [`bot_actions`](/Users/k20037673/Desktop/test claude/infrastructure_v2/bot_actions): reusable actions invoked before/after steps
- [`shared`](/Users/k20037673/Desktop/test claude/infrastructure_v2/shared): prompt builders, LLM helpers, storage helpers

Current reference apps:

- [`apps/micronarratives`](/Users/k20037673/Desktop/test claude/infrastructure_v2/apps/micronarratives)
- [`apps/double_micronarratives`](/Users/k20037673/Desktop/test claude/infrastructure_v2/apps/double_micronarratives)

## Runtime Model

The shared step runtime lives in [`core/step_runner.py`](/Users/k20037673/Desktop/test claude/infrastructure_v2/core/step_runner.py).

At a high level, `run_step(...)` does this:

1. build the step config from the `StepSpec`
2. if the step is in a chat post-processing phase, run the dedicated post-chat flow
3. run `before_actions` once
4. render the step UI for its mode
5. apply updates from the UI event
6. run matching `after_actions`
7. return whether the step is still waiting or completed

Important runtime rules:

- every step declares the state keys it may read/write
- updates to undeclared keys raise a `ConfigError`
- shared system/runtime keys live under `__system__.`
- chat steps with `post_chat` support have an explicit “finished chat -> generate outputs -> continue” phase

## Session State Model

The shared session wrapper is [`core/session.py`](/Users/k20037673/Desktop/test claude/infrastructure_v2/core/session.py).

Apps work with an `AppContext`, which namespaces everything under the app name inside Streamlit session state.

`AppContext` gives you:

- `init_defaults(...)`
- `get(...)`
- `set(...)`
- `update(...)`
- `append_message(...)`
- `clear_many(...)`
- `items()`

Practical consequence:

- app state keys are plain strings like `transcript`, `final_scenario`, `rating`
- the actual Streamlit session key is namespaced automatically

## Step Specs

The shared step-spec helpers live in [`core/step_specs.py`](/Users/k20037673/Desktop/test claude/infrastructure_v2/core/step_specs.py).

The central objects are:

- `StepSpec`: one runtime step contract
- `ActionSpec`: one reusable action invocation

`StepSpec` contains:

- `id`
- `mode`
- `content_path`
- `reads`
- `writes`
- `ui`
- `model`
- `before_actions`
- `after_actions`

## Supported Step Modes

The currently supported modes are:

- `accept`
- `text`
- `choice`
- `rating`
- `selection`
- `iterative_selection`
- `edit`
- `progress`
- `multi_field_form`
- `card_builder`
- `generate`

The shared renderers live in [`core/renderers.py`](/Users/k20037673/Desktop/test claude/infrastructure_v2/core/renderers.py).

### `accept`

Use for:

- consent/acknowledgement/continue pages
- simple final pages

Typical TOML/UI fields:

- `title`
- `body`
- `button_label`
- optional `response_key`

### `text`

Two variants exist:

- standard text input form
- chat mode

Standard text input is used for:

- participant ID pages
- one-off text response pages

Chat mode is enabled by `ui.input_style = "chat"` and is what powers the guided LLM conversation flow.

### `choice`

Use for:

- radio selection among a small set of simple options

### `rating`

Use for:

- rating a selected/generated piece of text
- slider-based judgments

The renderer supports:

- displayed context text
- prompt
- low/high labels
- min/max/default

### `selection`

Use for:

- choosing one generated scenario/narrative/option from a list

Behavior:

- renders each option in a bordered container
- supports auto-select when there is only one option

### `iterative_selection`

Use for:

- yes/no option picking
- random cycling through one option at a time
- flows where seeing the full list at once is not desirable

Behavior:

- shows exactly one option at a time
- `No` rejects the current option and randomly shows another unseen option
- `Yes` stores the current option as the selected value and completes the step
- supports an exhausted state if all options have been rejected

### `edit`

Use for:

- editable narrative/scenario revision
- manual editing plus “adapt with AI”

Behavior:

- editable text area
- reset to original
- AI chat-like adaptation request
- accept/reject suggestion flow

### `progress`

Reserved for progress-style pages. It exists in the supported renderer map, but is not one of the main patterns used by the current apps.

### `multi_field_form`

Use for:

- pages that combine several structured fields on one screen
- reflection/evaluation pages

Supports:

- `context_state_keys` from app code
- multiple context blocks shown in bordered containers
- ordered `ui.fields`
- currently supported field types:
  - `rating`
  - `text`
  - `single_choice`
  - `multiple_choice`

Validation behavior:

- all field types are treated as required by default
- each field can override its required-message copy
- app code can optionally pass a `validator` callable through the step spec
- the validator receives `(updates, context)`
- it may return:
  - `None` to allow submission
  - a non-empty string to block submission and show that exact message
  - `False` to block submission and use `ui.validation_error_message` if provided

This keeps the module reusable without hardcoding every app's validation logic into the infrastructure.

The contract for this step is ordered `fields`. Each field declares its own `type` and `response_key`.

### `card_builder`

Use for:

- guided structured authoring with a live/generated preview

Behavior:

- render one or more context blocks
- ask a sequence of questions
- store committed answers
- regenerate the preview after each committed answer
- allow finishing only once all questions have answers

### `generate`

Use for:

- one-shot contextual generation pages
- “show context -> click generate -> review generated result -> continue”

Supports:

- `context_state_keys` from app code
- one generated output state
- generation action on button click

## Shared Actions

The action registry lives in [`bot_actions/registry.py`](/Users/k20037673/Desktop/test claude/infrastructure_v2/bot_actions/registry.py).

Current shared actions:

- `load_previous_scenario`
- `initialize_chat`
- `conversation_turn`
- `summarize_conversation`
- `generate_scenarios`
- `generate_single_narrative`
- `generate_adaptation`
- `generate_contextual_rewrite`
- `generate_card`
- `package_session`
- `save_session`

### `load_previous_scenario`

Reads a previously saved scenario from storage using a participant ID.

Typical use:

- optional study flows that depend on a previous saved output

### `initialize_chat`

Seeds the transcript with the assistant intro.

It also supports inserting a previous scenario into intros via the `STORY-HERE` placeholder.

### `conversation_turn`

Runs one LLM turn of a guided chat.

Behavior:

- takes transcript history and latest user input
- builds the questions prompt
- appends the new user message
- appends the assistant reply
- if the model returns `FINISHED`, marks the chat as complete

### `summarize_conversation`

Runs an extraction prompt over the finished transcript and produces a structured summary dict.

Important behavior:

- it uses the configured `summary.questions`
- it always uses the LLM extraction path
- it normalizes `null`/`"null"` values to empty strings

### `generate_scenarios`

Generates 1 to 3 scenarios from:

- summary answers
- summary questions
- generation personas
- one-shot example

Output is a list stored in state.

### `generate_single_narrative`

Same idea as `generate_scenarios`, but the JSON output key is `output_narrative` and the state contract is aimed at narrative flows.

Even though the name says “single”, it still supports 1 to 3 personas and returns a list of generated narratives.

### `generate_adaptation`

Produces a revised version of an existing scenario/narrative based on a user request.

This powers the shared edit-step AI adaptation flow.

### `generate_contextual_rewrite`

Rewrites a narrative through a selected context/lens.

The shared contract is intentionally generic:

- source narrative
- one generic `context` string
- rewritten output

### `generate_card`

Generates a compact output card from:

- one generic `context` string
- structured question/answer input

The answers are formatted for the prompt as:

```text
Question: ...
Answer: ...
```

### `package_session`

Builds a saveable payload from app state.

It always includes:

- `session_id`
- `participant_id`
- `completion_time`
- `final_scenario`

Then it can copy additional fields listed by the step config.

### `save_session`

Writes a packaged payload to DynamoDB using the configured table service.

## Prompt Builders

Shared prompt builders live in [`shared/prompt_builders.py`](/Users/k20037673/Desktop/test claude/infrastructure_v2/shared/prompt_builders.py).

Current shared prompt families:

- question collection
- summary extraction
- scenario generation
- single narrative generation
- adaptation
- contextual rewrite
- card generation

The prompt/content split is:

- shared Python builds the prompt templates
- app TOML provides the app-specific persona, questions, examples, and guidance

## App Wiring Pattern

The normal pattern for an app is:

1. define a step enum in `app.py`
2. initialize session defaults in `init_app_context(...)`
3. build `step_specs` in `step_specs.py`
4. call `run_step(...)`
5. move to the next step in app code once a step completes

The reference example is [`apps/micronarratives/step_specs.py`](/Users/k20037673/Desktop/test claude/infrastructure_v2/apps/micronarratives/step_specs.py).

That app shows the standard pattern:

1. `consent`
2. `identify`
3. `story_chat`
4. `scenario_select`
5. `scenario_rating`
6. `scenario_adaptation`
7. `completion`

The point of the framework is that:

- the **flow** stays in app code
- the **step mechanics** stay shared

## TOML Content Structure

TOML files are content/config files, not full runtime definitions.

Typical sections you will see:

- `[ui]`
- `[bot]`
- `[summary]`
- `[generation]`
- `[adaptation]`
- `[rewrite]`
- `[card_generation]`

Examples:

- `story_chat` steps usually contain:
  - `[ui]`
  - `[bot]`
  - `[summary]`
  - `[generation]`

- adaptation/edit steps usually contain:
  - `[ui]`
  - `[adaptation]`

- contextual rewrite steps usually contain:
  - `[ui]`
  - `[rewrite]`

- card builder steps usually contain:
  - `[ui]`
  - `[[ui.questions]]`
  - `[card_generation]`

The rule of thumb is:

- if it is copy, prompt guidance, examples, or display content, it belongs in TOML
- if it is state wiring, trigger wiring, or flow logic, it belongs in Python

## Service Layer

Shared infrastructure can receive services from the app entrypoint.

Current common service:

- `table_write`

Storage helpers live in [`shared/storage.py`](/Users/k20037673/Desktop/test claude/infrastructure_v2/shared/storage.py).

Relevant functions:

- `get_table(...)`
- `save_item(...)`
- `fetch_latest_by_participant(...)`

## What Is Reusable vs App-Specific

### Keep shared

- runtime behavior
- step renderers
- generic LLM actions
- prompt template builders
- storage helpers
- state-key helpers

### Keep app-specific

- step order
- session defaults
- which state keys a step reads/writes
- which actions run on which triggers
- which context blocks a page displays
- app-specific copy and prompt content

## How To Add A New App

Typical process:

1. create `apps/<new_app>/`
2. create `app.py`
3. create `step_specs.py`
4. create `steps/*.toml`
5. define your app state defaults
6. define your step sequence and transitions
7. wire each step to shared modes/actions

Recommended approach:

- start from `apps/micronarratives` if your flow is narrative-first
- start from `apps/double_micronarratives` if your flow has two linked passes
- only add new shared infrastructure when the need is truly reusable across apps

## Current Architectural Direction

This repository is intentionally moving toward:

- cleaner shared step contracts
- more general context display patterns
- fewer app-specific assumptions in shared code
- more reusable “modules” built from:
  - renderer mode
  - action wiring
  - TOML content
  - app-level state mapping

The practical standard for adding functionality is:

- first ask whether it belongs in app code
- only move it into shared infrastructure if it clearly improves reuse across multiple apps
