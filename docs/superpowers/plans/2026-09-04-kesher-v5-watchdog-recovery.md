# Kesher V5 Watchdog Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add progress-aware recovery to the V5 Kesher controller without ever creating duplicate article sessions or duplicate NotebookLM provider generations.

**Architecture:** The existing `Kesher Content Controller` remains the single owner. A five-minute recovery heartbeat observes durable stage identity and progress; Article recovery nudges and, only with an authoritative live Jules session, restarts the GitHub worker so it resumes that same session. Video/Short recovery is identity-preserving and never generates a second provider artifact once provider identity exists.

**Tech Stack:** Python 3, GitHub Actions, Jules v1alpha API, existing Kesher V5 controller/state artifacts.

**Spec:** Approved in-chat design from 2026-09-04.

## Global Constraints

- Controller remains the only scheduler and mutation owner.
- Heartbeat cadence is five minutes while successful progress remains event-driven.
- Article: 15 minutes no progress -> one nudge; about 25 minutes -> restart GitHub worker only, preserving exact Jules session/slot.
- Never start a second Jules session while an authoritative one is active.
- Long video: provider identity (`source_id`, `task_id`, `artifact_id`) is immutable; recovery is resume-only once present.
- Short always uses `operation=derive` from the exact long-form identity; never `full` during recovery.
- YouTube recovery verifies the existing `youtube_video_id`; it does not re-upload merely because processing is slow.
- Controller completion still requires article public + long video public/processed + Short public/processed + shared provider identity.

---

### Task 1: Article Watchdog
- [ ] Add failing tests for 5-minute heartbeat, 15-minute same-session nudge, 25-minute worker-only restart, idempotent nudge, and fail-closed missing Jules identity.
- [ ] Implement durable watchdog state and article progress fingerprint.
- [ ] Add Jules same-session snapshot/nudge methods and GitHub worker cancel/re-dispatch.
- [ ] Keep the 55-minute article workflow hard ceiling unchanged.
- [ ] Verify focused tests and PR CI.

### Task 2: Video + Short Watchdog
- [ ] Add failing tests proving provider identity can only resume, never regenerate.
- [ ] Add long-video 20-minute diagnostic / 30-minute worker recovery and 90-minute hard ceiling.
- [ ] Add Short 15/25-minute diagnose/restart using derive-only semantics and 60-minute hard ceiling.
- [ ] Add YouTube processing-state recovery without duplicate upload.
- [ ] Verify focused tests and PR CI.

### Task 3: Production Verification
- [ ] Merge only after checks pass.
- [ ] Continue the existing `2026-09-04` cycle; do not start a different article.
- [ ] Verify one article, one NotebookLM provider generation, one regular YouTube video, one Short, same provider identity, and zero duplicates.
