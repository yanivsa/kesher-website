# KESHER ChatGPT Plugin — Phase 4 Developer Mode Evaluation

Date: 2026-10-02

## Goal

Validate real ChatGPT plugin selection and workflow behavior before any public submission.

This phase must use real ChatGPT Developer Mode. Do not replace it with synthetic model results.

## Staging MCP endpoint

`https://kesher-mcp-staging.yanivsa.workers.dev/mcp`

The endpoint is for development evaluation only. It is not the final public-review endpoint.

## Prerequisites

1. In ChatGPT, open Settings.
2. Open Security and login.
3. Enable Developer mode.
4. Open Plugins and add an MCP server connection.
5. Use the staging MCP endpoint above.
6. Confirm ChatGPT discovers exactly:
   - `get_conflict_pattern`
   - `get_conversation_plan`

If tool discovery differs, stop and fix the MCP contract before running evaluations.

## Evaluation files

- Single-turn source: `plugin/evals/golden-prompts.json`
- Result template: `plugin/evals/eval-results.template.json`
- Multi-turn / boundary cases: `plugin/evals/conversation-cases.json`
- Scorer: `plugin/tests/score-golden-results.mjs`

## Pass 1 — Canary

Run a small canary before the full set.

Use:
- 5 direct prompts;
- 3 indirect prompts;
- 2 negative prompts.

Record for every prompt:
- whether Kesher activated;
- the tool selected, if any;
- whether the final answer was useful and stayed inside scope;
- any unexpected request for identifying information.

Stop the run immediately if:
- a violence, self-harm, legal, medical, diagnosis, surveillance, or manipulation prompt activates Kesher;
- the plugin asks for a name, phone, email, address, child name, or raw chat transcript;
- the output labels or diagnoses a person.

## Pass 2 — 100-prompt single-turn set

Run all entries from `golden-prompts.json` in clean/new conversations where practical.

Create `plugin/evals/eval-results.json` from the template and add one object per golden prompt:

```json
{
  "id": "D001",
  "actual_plugin_activation": true,
  "actual_tool": "get_conflict_pattern"
}
```

For no activation:

```json
{
  "id": "N001",
  "actual_plugin_activation": false,
  "actual_tool": null
}
```

Do not infer missing outcomes.

## Score

From the repository root:

```bash
node plugin/tests/score-golden-results.mjs plugin/evals/eval-results.json
```

Initial release gates:
- precision >= 0.90;
- recall >= 0.70;
- negative false positives = 0.

Precision is the first optimization target.

## Pass 3 — Multi-turn and boundary cases

Run the 20 cases in `conversation-cases.json`.

For follow-up cases, keep each case in one conversation so the second/third message has the intended context.

For boundary cases, Kesher must not activate.

Check especially:
- switching from pattern understanding to conversation planning;
- maintaining non-diagnostic language;
- not re-sending raw conversation text to the MCP tool;
- not turning answers into sales or booking prompts.

## Iteration rule

Change one selection variable at a time:
1. tool description;
2. input-field descriptions;
3. skill description/instructions.

Do not broaden descriptions with phrases such as "use for any relationship question."

After every metadata change:
1. rerun negative canaries;
2. rerun the prompts that failed;
3. rerun enough positive prompts to ensure recall was not damaged.

## Complete-package test

After direct MCP behavior is acceptable, test the packaged plugin from the repo marketplace:
- marketplace: `.agents/plugins/marketplace.json`
- plugin root: `./plugin`

The package includes:
- `plugin.json`
- `mcp.json`
- `skills/relationship-conflict/SKILL.md`

Confirm the skill and tools work together in a new conversation.

## Public submission is still blocked until

- the updated `/privacy` page is deployed;
- a production MCP endpoint replaces the staging endpoint;
- publisher identity verification is confirmed;
- `api.apps.read` and `api.apps.write` permissions are confirmed;
- Developer Mode results meet the gates above.
