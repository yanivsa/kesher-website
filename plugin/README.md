# Kesher Hebrew Relationship Tools

Development package for the KESHER ChatGPT/Codex plugin.

## Current status

- Portable Agent Plugin manifest: `plugin.json`
- Remote MCP config: `mcp.json`
- Workflow skill: `skills/relationship-conflict/SKILL.md`
- MCP Worker source: `src/index.mjs`
- Deterministic domain logic: `src/domain.mjs`
- 100 single-turn Hebrew eval prompts
- 20 multi-turn/boundary eval cases
- Cloudflare staging endpoint:
  `https://kesher-mcp-staging.yanivsa.workers.dev/mcp`

## Local validation

From the repository root:

```bash
node plugin/tests/validate-phase2-contracts.mjs
node plugin/tests/domain.test.mjs
node plugin/tests/validate-plugin-package.mjs
node plugin/tests/validate-skill-evals.mjs
node plugin/tests/score-golden-results.mjs --self-test
npm ci --prefix plugin
npm --prefix plugin run check
```

## Real ChatGPT evaluation

Follow `docs/chatgpt-plugin/phase-4-developer-mode-runbook.md`.

Synthetic scorer self-tests prove only that the evaluator works. They are not evidence of real ChatGPT tool selection.

## Public-review note

The current `workers.dev` server is staging. Do not submit it as the final production MCP endpoint.
