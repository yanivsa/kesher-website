# KESHER ChatGPT Plugin — Phase 2 MCP Contract

Date: 2026-10-02  
Branch: `feature/kesher-chatgpt-plugin`

## Product boundary

V1 solves one job only:

> Help a Hebrew-speaking adult structure understanding of a recurring couple-communication conflict and prepare a calmer next conversation.

V1 does not diagnose people, evaluate whether a relationship should continue, provide legal/medical/crisis advice, or collect lead/contact details.

## Data-minimization rule

The MCP server MUST NOT request:
- full conversation history;
- raw chat transcript;
- partner names;
- phone, email, address;
- child names;
- free-form intimate narrative.

ChatGPT should map the user's request to bounded enums before tool invocation.

## Public MCP tools

### 1. `get_conflict_pattern`

**Title:** מיפוי דפוס קונפליקט זוגי

**Selection description:**

Use when a Hebrew-speaking adult wants a structured explanation of a recurring couple-communication conflict and the interaction has already been reduced to a topic and observable conversation signals. Returns a non-diagnostic description of the interaction cycle and one practical next step. Do not use for legal/divorce questions, medical or sexual-health advice, diagnosis of a partner, domestic violence or immediate danger, self-harm, surveillance, coercion/manipulation, generic relationship information, or romantic writing.

**Annotations**
- `readOnlyHint: true`
- `destructiveHint: false`
- `openWorldHint: false`
- `idempotentHint: true`

**Privacy**
No raw user narrative is accepted.

### 2. `get_conversation_plan`

**Title:** תכנון שיחה זוגית רגועה

**Selection description:**

Use when a Hebrew-speaking adult wants a short, structured plan for opening or restarting a difficult conversation with a partner after the topic, goal, emotional intensity, and likely interaction risk are already known. Returns a suggested opening, ordered steps, a pause phrase, a repair phrase, and phrases to avoid. Do not use for legal/divorce negotiation, threats or violence, self-harm, medical or sexual-health advice, diagnosis, surveillance, coercion/manipulation, or requests to pressure a partner into compliance.

**Annotations**
- `readOnlyHint: true`
- `destructiveHint: false`
- `openWorldHint: false`
- `idempotentHint: true`

**Privacy**
No raw transcript or identifying personal data is accepted.

## Routing principle

The model should choose `get_conflict_pattern` when the main user need is "help me understand what keeps happening."

The model should choose `get_conversation_plan` when the main user need is "help me say/open/restart this conversation."

If neither need is present, the plugin should not activate.

## Safety boundary

The following categories are hard out-of-scope for V1 and are represented in the negative evaluation set:
- domestic violence / immediate danger;
- self-harm / suicidality;
- legal/divorce rights and proceedings;
- medical or sexual-health diagnosis/treatment;
- psychiatric/personality diagnosis;
- surveillance, unauthorized access or tracking;
- coercive or manipulative tactics.

The MCP tools do not attempt to handle these cases. Correct behavior is non-selection.

## Open-world annotation rationale

Both V1 tools compute from bounded, versioned Kesher guidance packaged with the server. They do not browse the public web, call open-ended external services, send messages, persist user state, or modify external systems. Therefore `openWorldHint=false` and `readOnlyHint=true` are accurate.

## Phase 2 acceptance criteria

- exactly two public tools;
- all tool inputs bounded by explicit schemas;
- no free-form narrative input;
- explicit boolean safety annotations;
- descriptions include positive intent and exclusions;
- all positive golden prompts route only to one of the two public tools;
- all negative golden prompts expect no activation;
- contract validator passes in CI.
