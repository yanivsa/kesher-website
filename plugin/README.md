# Kesher — Hebrew Relationship & Parenting Tools

Development package for the KESHER ChatGPT Plugin V2.

## V2 surface

Five read-only MCP tools:
- `get_conflict_pattern`
- `get_conversation_plan`
- `get_parenting_response_plan`
- `get_adhd_parenting_plan`
- `find_kesher_resource`

Three workflow Skills:
- relationship conflict
- parenting guidance
- attention / executive-function parenting

Evaluation assets:
- 220 single-turn Hebrew prompts
- 30 multi-turn/boundary cases
- domain-specific precision/recall gates

The ADHD/executive-function workflow is parenting support only. It does not diagnose ADHD and does not provide medication advice.

## Content intelligence

`scripts/generate-plugin-resources.mjs` builds `plugin/data/kesher-resources.json` from the site's current canonical posts plus three explicit Kesher service pages (couples, parenting, and parenting ADHD). The MCP resource tool searches only this bounded Kesher index.

## Staging

`https://kesher-mcp-v2-staging.yanivsa.workers.dev/mcp`

V2 uses an isolated staging Worker so the older V1 branch cannot overwrite the environment used for Developer Mode evaluation.

Staging only. Do not submit it as the final public production endpoint.
