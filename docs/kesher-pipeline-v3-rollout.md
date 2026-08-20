# Kesher Production Pipeline v3 rollout

This rollout replaces incremental production patching with a staged contract-driven migration.

## Phase A — Contract
- one canonical production contract
- controller-owned scheduling and retries
- technical video publication gate
- advisory Jules video review
- FIFO video queue
- 3 durable video-state snapshots, retained for 14 days
- image is a required production stage with a guaranteed local fallback

## Phase B — Video topology cleanup
- remove compatibility aliases and legacy mandatory-Jules workflow wording
- ensure Jules review failures never block a technically valid upload
- align artifact retention with the contract

## Phase C — Image pipeline v2
- move image creation to a dedicated GitHub Actions worker
- use current Gemini image generation, then stock providers, then a local guaranteed fallback
- persist provider/model/attempt/hash/validation metadata
- never publish a new article without an image

## Phase D — Controller/state consolidation
- explicit state machine
- provider IDs persisted before follow-up side effects
- deterministic operation IDs and resume-before-create behavior
- controller is the only business retry owner

## Phase E — failure simulation
- duplicate event ordering
- provider timeouts
- worker cancellation
- crash after provider creation
- crash after YouTube ID
- backlog recovery
- corrupted artifact handling

## Acceptance
Production is considered stable only after seven consecutive publication cycles with one article, one image and one public verified YouTube video per cycle, zero duplicate provider objects, zero duplicate uploads and no manual retry.
