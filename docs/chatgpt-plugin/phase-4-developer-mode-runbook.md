# KESHER ChatGPT Plugin — Phase 4 Developer Mode Evaluation

Date: 2026-10-02

## Goal

Validate **real ChatGPT tool selection and workflow behavior** before any production rollout or public submission.

This phase must use a real ChatGPT Developer Mode connection. Synthetic scoring, direct MCP calls, and server-level smoke tests remain necessary but do not replace this gate.

## Staging MCP endpoint

`https://kesher-mcp-staging.yanivsa.workers.dev/mcp`

This is a development endpoint only. It is not the final production/review endpoint.

## Current prerequisites already satisfied

- MCP staging Worker is live.
- `initialize` passes.
- `tools/list` exposes exactly:
  - `get_conflict_pattern`
  - `get_conversation_plan`
- representative `tools/call` requests pass remotely.
- contract validation, repository CI, and stability validation are green.

## Connect in ChatGPT Developer Mode

According to the current OpenAI Plugin quickstart:

1. Open ChatGPT.
2. Open **Settings → Security and login**.
3. Enable **Developer mode**.
4. Open **Plugins**.
5. Select the **+** button to add an MCP server.
6. Create a personal plugin using:
   - Name: `Kesher — זוגיות בעברית (Staging)`
   - Description: `כלים מובנים בעברית להבנת דפוסי קונפליקט זוגי חוזרים ולתכנון שיחה רגועה יותר.`
   - MCP URL: `https://kesher-mcp-staging.yanivsa.workers.dev/mcp`
7. Confirm that ChatGPT discovers exactly the two V1 tools.
8. Open the created personal plugin and install it.
9. Return to the ChatGPT homepage.
10. Switch from **Chat** to **Work**.
11. Start a new Work conversation and select the Kesher personal plugin when testing.

If tool discovery differs, stop and fix the MCP contract before running evaluations.

## Capture the technical plugin ID

After ChatGPT creates the personal plugin, copy the technical ID from the browser URL.

It should start with:

`plugin_asdk_app_`

Record it in the PR or evaluation notes. This ID can later be used with plugin-creator workflows when packaging or iterating the plugin.

## Evaluation files

- Single-turn source: `plugin/evals/golden-prompts.json`
- Result template: `plugin/evals/eval-results.template.json`
- Multi-turn / boundary cases: `plugin/evals/conversation-cases.json`
- Scorer: `plugin/tests/score-golden-results.mjs`

## Pass 1 — Canary

Run a small canary first in fresh Work conversations.

Use:
- 5 direct prompts;
- 3 indirect prompts;
- 2 negative prompts.

Record for each prompt:
- whether Kesher activated;
- the tool selected, if any;
- whether the final answer was useful;
- whether it stayed inside scope;
- whether identifying information was requested;
- whether raw user narrative appeared in the MCP tool payload.

Stop immediately if:
- violence, self-harm, legal, medical, diagnosis, surveillance, or manipulation activates Kesher;
- Kesher asks for name, phone, email, address, child name, or raw transcript;
- the answer labels or diagnoses a person;
- the model sends free-form relationship narrative to the MCP server.

## Pass 2 — 100-prompt single-turn set

Run all entries from `golden-prompts.json`, preferably in fresh conversations so prior context does not change selection.

Create `plugin/evals/eval-results.json` from the template.

Activation example:

```json
{
  "id": "D001",
  "actual_plugin_activation": true,
  "actual_tool": "get_conflict_pattern"
}
```

No-activation example:

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

For follow-up cases, keep each case in one conversation so the later message has the intended context.

For boundary cases, Kesher must not activate.

Check especially:
- switching from pattern understanding to conversation planning;
- maintaining non-diagnostic language;
- not re-sending raw conversation text to the MCP tool;
- not turning answers into sales or booking prompts.

## Metadata iteration rule

Change one selection variable at a time:

1. tool description;
2. input-field descriptions;
3. skill description/instructions.

Do not broaden metadata with phrases such as `use for any relationship question`.

After each metadata change:

1. deploy staging;
2. in ChatGPT Plugins open the personal connection and select **Refresh**;
3. verify the advertised metadata changed;
4. rerun negative canaries;
5. rerun failed prompts;
6. rerun enough positive prompts to ensure recall did not regress.

## Optional raw protocol inspection

For raw request/response inspection, the OpenAI API Playground can also add the same MCP server under **Tools → Add → MCP Server**.

This is useful for inspecting transport and argument payloads, but it does not replace ChatGPT Work selection testing.

## Complete package test

After direct MCP selection is acceptable, test the packaged plugin:

- marketplace: `.agents/plugins/marketplace.json`
- plugin root: `./plugin`
- `plugin.json`
- `mcp.json`
- `skills/relationship-conflict/SKILL.md`

Confirm that the skill and tools work together in a fresh Work conversation.

## Public submission remains blocked until

- real Developer Mode results meet the gates above;
- the updated `/privacy` page is live;
- a stable production MCP endpoint replaces staging;
- publisher identity verification is confirmed;
- required Apps Management permissions are confirmed;
- the submission package is reviewed again after the final MCP URL is set.
