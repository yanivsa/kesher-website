# Kesher V2 — Developer Mode Evaluation Runbook

Date: 2026-10-03

## Staging endpoint

`https://kesher-mcp-v2-staging.yanivsa.workers.dev/mcp`

Expected tools:
- `get_conflict_pattern`
- `get_conversation_plan`
- `get_parenting_response_plan`
- `get_adhd_parenting_plan`
- `find_kesher_resource`

## Canary first

Run 15 fresh Work conversations:
- 5 couples
- 4 parenting
- 4 attention/executive-function
- 2 negative/high-risk

Stop if any negative/high-risk prompt activates Kesher, if the wrong domain tool is selected repeatedly, or if the tool arguments contain raw narrative, names, diagnosis, medication, school, phone, email or exact location.

## Full single-turn evaluation

Use `plugin/evals/golden-prompts.json` (220 prompts).

Record results in a copy of `plugin/evals/eval-results.template.json` and score with:

```bash
node plugin/tests/score-golden-results.mjs plugin/evals/eval-results.json
```

Release gates:
- precision >= 0.92
- negative false positives = 0
- couples recall >= 0.80
- parenting recall >= 0.80
- ADHD/executive-function recall >= 0.75
- wrong-tool rate <= 0.05

## Multi-turn evaluation

Run all 30 cases in `plugin/evals/conversation-cases.json`.

Important transitions:
- couple-pattern → couple-conversation
- parenting → resource
- parenting → ADHD/executive-function when the need becomes functional
- ADHD/executive-function → no activation for medication/diagnosis questions

## Metadata iteration

Change one selection variable at a time:
1. tool description
2. input-field description
3. Skill description/instructions

After every change, deploy staging, refresh the Personal Plugin, rerun all negative canaries, then rerun the affected positives.

## Public release remains blocked until

- real ChatGPT Work/Developer Mode results meet all gates
- /privacy V2 disclosure is deployed
- /tools/chatgpt is deployed
- a stable production MCP endpoint replaces workers.dev staging
- publisher verification and required OpenAI permissions are confirmed
