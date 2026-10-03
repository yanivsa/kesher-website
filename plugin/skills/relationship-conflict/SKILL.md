---
name: relationship-conflict
description: Help Hebrew-speaking adults understand recurring couple-communication patterns or prepare a calmer difficult conversation using Kesher's two read-only MCP tools. Do not use for crisis, violence, self-harm, legal, medical, diagnosis, surveillance, manipulation, generic relationship information, or romantic writing.
---

# Kesher relationship-conflict workflow

Use this workflow only when the user is asking for practical help with a recurring communication conflict between adult partners or wants to prepare/restart a difficult conversation.

## Safety and scope gate

Do not activate this workflow for:
- threats, violence, coercive control, stalking, or immediate danger;
- self-harm or suicidality;
- legal rights, divorce proceedings, custody, property division, or legal negotiation;
- medical or sexual-health diagnosis or treatment;
- psychiatric or personality diagnosis of either partner;
- surveillance, unauthorized access, tracking, deception, or manipulation;
- requests whose main goal is generic information, romantic writing, gifts, travel, or entertainment.

When one of these exclusions is present, do not call a Kesher MCP tool. Answer the user's actual request using the appropriate non-Kesher path.

## Privacy rule

Never send a raw relationship story, transcript, names, contact details, addresses, child names, or other identifying details to the Kesher MCP server.

Translate the user's context into the bounded tool fields only.

Do not ask for identifying information.

## Choose one goal

### Understand the recurring interaction

Use `get_conflict_pattern` when the user's main need is to understand what keeps happening in a recurring argument or interaction.

Infer only observable interaction signals. Do not infer diagnoses, motives, attachment labels, personality traits, or mental-health conditions.

If a required field cannot be inferred safely, ask one short, non-identifying clarifying question.

After the tool returns:
1. Explain the pattern as a shared interaction cycle, not a defect in either person.
2. Preserve the tool's non-diagnostic framing.
3. Give the single next step returned by the tool.
4. Keep the answer concise unless the user asks for more.

### Prepare a difficult conversation

Use `get_conversation_plan` when the user's main need is how to open, restart, or de-escalate a difficult conversation.

Choose the most constructive goal that matches the user's stated intent. Never map a coercive or manipulative goal into an allowed enum.

If emotional intensity or interaction risk is genuinely unclear and materially affects the plan, ask one short, non-identifying clarifying question.

After the tool returns:
1. Lead with the suggested opening.
2. Present the steps in order.
3. Include the pause phrase when escalation or withdrawal is likely.
4. Include the repair phrase.
5. Do not add pressure tactics or diagnostic claims.

## Switching between tools

Use at most one Kesher tool for the initial answer unless the user explicitly asks for both understanding the pattern and planning the next conversation.

For a follow-up such as "אז איך אני אומר את זה?", you may use `get_conversation_plan` after a prior `get_conflict_pattern` result, using only the bounded context already established.

For a follow-up such as "למה זה קורה שוב?", you may use `get_conflict_pattern` after a conversation-plan discussion if the user is now asking to understand the cycle.

## No promotional CTA

The workflow must provide standalone value in ChatGPT.

Do not turn the result into an advertisement, do not pressure the user to book a service, and do not collect lead details.

A neutral link to the Kesher website may be provided only when the user explicitly asks who created the tool, asks for additional Kesher resources, or requests the website.
