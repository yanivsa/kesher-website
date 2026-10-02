# KESHER ChatGPT Plugin — Phase 0/1 Baseline & Intent Research

Date: 2026-10-02
Branch: `feature/kesher-chatgpt-plugin`
Baseline main SHA: `839c9a8c15ede02956d02931cc55ac6bfd4b16a0`

## Phase 0 — Baseline

The implementation branch was created from the exact current `main` SHA above.

Observed baseline on that SHA:
- GitHub Actions `CI` run `36985020496`: **success**.
- GitHub Actions `Deploy to Cloudflare Pages` run `36985020427`: **success**.
- `ci.yml` runs the repository's full quality gate (`npm run check`) on `main`.
- The workflow supports `workflow_dispatch` on feature branches and selects a CI profile from the branch diff.

This gives the plugin work a known-green starting point and isolates it from unrelated failures.

## Phase 1 — Intent discovery

### Initial competition signal

A Plugin Directory discovery check for the Hebrew terms:
- `ייעוץ זוגי`
- `הדרכת הורים`
- `זוגיות הורות ישראל`

returned no relevant Hebrew plugins in the current directory search. This is an opportunity signal, not proof that no competition exists.

### V1 scope

V1 targets one narrow job:
**help a Hebrew-speaking user understand a recurring couple-communication conflict and/or structure a calmer next conversation.**

V1 is not:
- diagnosis or assessment of a person/partner;
- crisis or domestic-violence support;
- medical or sexual-health advice;
- legal/divorce advice;
- surveillance or coercive/manipulative assistance;
- generic romantic content;
- a general couples-therapy encyclopedia.

### Golden Prompt Set

File: `plugin/evals/golden-prompts.json`

Distribution:
- 30 direct prompts.
- 40 indirect prompts.
- 30 negative prompts.
- 100 unique prompts total.

Primary clusters in the positive set:
- recurring conflict;
- criticism/defensiveness;
- pursue/withdraw cycles;
- escalation;
- failed repair attempts;
- money;
- household load;
- parenting disagreements;
- extended family;
- attention/connection;
- trust;
- difficult-conversation opening and de-escalation.

Negative-set categories deliberately include:
- divorce/legal;
- diagnosis;
- medical;
- violence/crisis;
- self-harm;
- surveillance;
- manipulation;
- generic information;
- unrelated requests.

### Evaluation rule

The first optimization target is **precision**, not maximum recall.

Initial acceptance thresholds:
- precision >= 0.90;
- recall >= 0.70;
- zero intentional activation on explicit crisis/violence/self-harm/legal/diagnosis/surveillance/manipulation test cases.

### Provisional tool-routing labels

Positive prompts are pre-labeled for one of two provisional V1 capabilities:
- `get_conflict_pattern`
- `get_conversation_plan`

These labels are intentionally provisional. Phase 2 should validate the product/tool boundary before MCP schemas are frozen.

## Phase 1 conclusion

Proceed to Phase 2 with a single MVP:
**Kesher — structured Hebrew support for recurring couple conflict and difficult-conversation planning.**

Do not broaden to parenting tools, lead submission, booking, legal workflows, diagnosis, or crisis handling until the first tool-selection and usefulness tests pass.
