# Infrastructure V2

`infrastructure_v2` is a framework for building guided intervention-style apps with a shared set of reusable interaction patterns.

It is aimed at people designing:

- reflective exercises
- narrative interventions
- structured self-inquiry tools
- psychoeducational flows
- reappraisal and reframing tools
- values or identity exploration tasks
- guided activities that mix user input with AI support

This repository is not one fixed intervention. It is a toolkit for assembling different interventions from a common structure.

If you want the implementation details, see [TECHNICAL_README.md](/Users/k20037673/Desktop/test claude/infrastructure_v2/TECHNICAL_README.md).

## What The Infrastructure Offers

At a high level, the framework gives you reusable building blocks for apps that need:

- multi-step flows
- guided conversations with a bot
- structured follow-up generation after a conversation
- narrative or scenario generation
- rating and selection steps
- editable text with “adapt with AI”
- reflection forms
- contextual rewriting
- structured card/profile/summary generation
- session packaging and database saving

The point is that you do not need to rebuild those mechanics every time.

## The Design Logic

The infrastructure is organized around **steps**.

Each step is one intervention moment, for example:

- consent
- participant ID input
- chat with the bot
- review several generated narratives
- rate one narrative
- edit it manually or with AI support
- reflect on a chosen character/persona
- generate a rewritten version
- generate a final card or takeaway
- save the final session

This lets an intervention be built as a sequence of psychologically meaningful moments, rather than one large app script.

## Types Of Step Experiences Available

The shared system currently supports several step patterns.

### Simple continue/consent steps

Useful for:

- consent pages
- introduction pages
- transition pages
- final acknowledgement pages

### Text input steps

Useful for:

- participant IDs
- short reflective responses
- one-off written answers

### Guided bot chat

Useful for:

- collecting a structured story
- eliciting examples and emotional detail
- asking a predefined set of questions in a conversational way

This is especially useful when you want the user to feel like they are having a guided exchange rather than filling out a rigid form.

### Post-chat summarisation and generation

After a guided chat, the infrastructure can:

- extract a structured summary from the conversation
- turn that summary into scenarios or narratives
- generate one or several options using different personas/voices

This is useful when the intervention needs to move from raw conversation into a more shaped or reflective output.

### Selection steps

Useful for:

- showing multiple generated options
- asking the participant to choose the one that feels closest or most useful

### Iterative yes/no selection

Useful for:

- presenting one option at a time
- letting the participant accept or reject each option
- cycling through possibilities until something feels right

This is useful when you want a simpler “yes/no/show me another one” interaction rather than a full selection list.

### Rating steps

Useful for:

- asking how accurate/helpful/appealing a generated output feels
- gating whether the user should continue directly or go to an adaptation step

### Editable narrative steps

Useful for:

- letting a participant manually refine a generated text
- letting them request an AI-supported change in a chat-like way

This is helpful for interventions where participant agency over wording matters.

### Reflection forms

Useful for:

- mixing several reflective questions on one page
- combining rating and open text reflection
- combining rating, open text, single-choice, and multiple-choice questions
- showing context above the form, such as a narrative or selected persona

Reflection forms can also include an optional app-defined validation rule when a page needs more than simple “all fields are filled in” logic.

### Contextual rewrite steps

Useful for:

- rewriting a narrative through a chosen lens
- changing stance, tone, or interpretation based on a selected frame

That frame could be:

- a superhero
- a future self
- a supportive peer
- a therapeutic stance
- a value-based lens
- any other contextual perspective

### Structured card/profile generation

Useful for:

- turning several short answers into a compact final artifact
- generating a coping card, identity card, reminder card, action card, or summary profile

## Types Of AI-Supported Actions Available

The infrastructure already supports several reusable AI-backed behaviors.

### Guided questioning

The bot can ask a predefined sequence of questions while staying conversational.

### Summary extraction

After a conversation, the AI can extract a structured summary into named fields.

### Scenario or narrative generation

The AI can turn structured answers into:

- scenarios
- short narratives
- multiple narrative variants using different personas

### Narrative adaptation

The AI can take an existing narrative and revise it based on a participant request while trying to preserve the original meaning and voice.

### Contextual rewriting

The AI can rewrite a narrative through a selected lens or perspective.

### Final card generation

The AI can combine structured answers and context into a final compact output, usually in markdown.

### Session packaging and saving

The infrastructure can package the relevant session outputs and save them to a database.

## What Makes This Useful For Intervention Design

For intervention designers, the useful thing is not just “there is a chatbot”.

The useful thing is that the framework supports a repeatable pattern:

1. collect a meaningful input
2. transform it into a psychologically useful intermediate representation
3. let the user evaluate or reshape it
4. generate a more actionable or resonant final output

This makes it suitable for interventions that rely on:

- self-reflection
- cognitive reframing
- narrative externalisation
- perspective-taking
- self-distancing
- values clarification
- coping-plan generation
- identity exploration

## What Is Configurable Without Rebuilding The Framework

An app creator can already change a lot without changing the shared infrastructure:

- page titles and body text
- bot persona and questioning style
- the actual questions asked
- what summary fields are extracted
- what personas are used for generation
- one-shot examples for generation
- adaptation prompts
- rewrite prompts
- card-generation prompts
- step ordering within an app
- which pieces of session state are shown as context on later pages

So the system is not only for “micronarratives”. That is just one reference use case.

## Current Reference App Types

The repository currently includes:

- a single-pass micronarratives app
- a two-pass/double micronarratives app

These demonstrate patterns like:

- one guided chat leading to several narrative options
- two linked chats where the first output seeds the second
- rating and adaptation gates
- completion packaging and saving

## How To Think About Building A New Intervention

A useful way to design a new app with this framework is:

1. decide the sequence of psychological moments you want the participant to go through
2. map each moment to an existing step type where possible
3. decide which outputs should carry forward as context
4. decide where AI should help:
   - questioning
   - summarising
   - generating
   - rewriting
   - adapting
5. decide what the final saved artifact should be

In practice, that often becomes something like:

1. consent
2. identification
3. guided story collection
4. generated narrative or scenario review
5. rating and refinement
6. reflection through a chosen lens
7. final output generation
8. save/finish

## For Developers

If you are implementing a new app or extending the shared system, start with:

- [TECHNICAL_README.md](/Users/k20037673/Desktop/test claude/infrastructure_v2/TECHNICAL_README.md)

That file explains:

- the runtime model
- step modes
- actions
- app wiring
- TOML structure
- storage and saving
