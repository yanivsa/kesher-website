# ChatGPT plugin submission audit — 2026-10-04

## Status

The earlier skills-only package under `chatgpt-plugin/` has been superseded by the canonical Kesher V2 Agent Plugin under `plugin/`.

The canonical package combines:
- 5 bounded read-only MCP tools;
- 3 scoped Skills;
- 220 Hebrew Golden Prompts;
- 30 multi-turn/boundary cases;
- a bounded Kesher resource index;
- privacy/safety guards and strict schemas.

The duplicate `chatgpt-plugin/` package was intentionally retired during reconciliation with current `main` so there is one public Kesher package identity and one submission path.

## Canonical paths

- Manifest: `plugin/plugin.json`
- MCP config: `plugin/mcp.json`
- Skills: `plugin/skills/`
- Staging MCP: `https://kesher-mcp-v2-staging.yanivsa.workers.dev/mcp`
- Developer Mode runbook: `docs/chatgpt-plugin/v2-developer-mode-runbook.md`
- Submission readiness: `plugin/review/submission-readiness.json`

## Automated gates

- `npm run plugin:validate`
- `npm run plugin:package`
- GitHub Actions: Kesher Plugin Contract Validation
- GitHub Actions: Kesher MCP Staging Deploy
- repository CI and stability validation

The package build includes only portable public artifacts:
`plugin.json`, `mcp.json`, `skills/`, and `assets/`.

## Remaining external gate

Do not publish or merge solely from synthetic tests. Connect the isolated V2 staging endpoint in ChatGPT Developer Mode / Work and run the canary, 220 single-turn prompts, and 30 conversation/boundary cases. Public submission remains blocked until those thresholds pass and the production MCP endpoint/domain is final.
