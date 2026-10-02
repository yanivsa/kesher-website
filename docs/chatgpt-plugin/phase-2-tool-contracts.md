# KESHER ChatGPT Plugin — Phase 2 Tool Contracts

Date: 2026-10-02

## Decision

V1 exposes exactly two read-only MCP tools:

1. `get_conflict_pattern` — turns bounded interaction signals into a neutral, non-diagnostic explanation of a recurring couple-conflict pattern.
2. `get_conversation_plan` — returns a short Hebrew plan for opening, repairing, or de-escalating a difficult couple conversation.

The contracts are declarative in `plugin/contracts/tools.json`. Runtime SDK implementation is intentionally deferred until these contracts are stable.

## Data minimization

Neither tool accepts raw chat text, transcripts, names, phone numbers, email addresses, exact locations, or other direct identifiers. ChatGPT should reduce the current request to bounded structured fields before the MCP call.

## Safety boundary

The V1 tools are not eligible for:
- violence or immediate safety concerns;
- self-harm;
- legal/divorce questions;
- medical or sexual-health questions;
- diagnosis of a user, partner, child, or family member;
- covert surveillance;
- coercive or manipulative tactics.

The explicit exclusions and logging constraints live in `plugin/contracts/safety-boundaries.json`.

## MCP annotations

Both tools are:
- `readOnlyHint: true`
- `destructiveHint: false`
- `openWorldHint: false`

They do not mutate state and the V1 contract does not access open-ended external entities.

## Metadata strategy

Descriptions begin with the intended usage condition and include explicit negative boundaries. The tool names are action-oriented and match the provisional labels already used by the 100-prompt Golden Set.

## QA

`tests/kesher-plugin-contracts.test.ts` validates:
- the exact two-tool surface;
- annotations;
- metadata boundaries;
- closed input/output schemas;
- absence of raw narrative / direct-identifier fields;
- synchronization with the Golden Prompt Set;
- high-risk exclusion coverage.

## Phase 3 entry criteria

Proceed to runtime MCP implementation only if:
- the repository full quality gate remains green;
- the two-tool contract passes its tests;
- no existing site behavior changes;
- no new write action, authentication requirement, or raw-prompt storage is introduced.
