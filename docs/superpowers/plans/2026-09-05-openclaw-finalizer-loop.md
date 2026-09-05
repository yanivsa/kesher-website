# OpenClaw Finalizer Loop Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the OpenClaw boot finalizer from restarting its own required gateway dependency, while preserving loopback-only port 18789, Cloudflare Access, and the existing Tailscale fallback path.

**Architecture:** Keep `openclaw-gateway.service` system-owned and loopback-only. Make `openclaw-offline-finalize.service` independent of the gateway unit lifecycle so the finalizer can safely start/restart the gateway, then prove RPC and write the ready file. Add explicit phase markers so any next failure is localized.

**Tech Stack:** Bash, systemd unit templates, Python unittest contract tests, GitHub Actions.

**Spec:** Issue #465 and current OpenClaw recovery workflow contracts.

## Global Constraints

- Never expose port 18789 publicly; gateway bind remains loopback.
- Never weaken Cloudflare Access.
- Preserve Tailscale as fallback; it must not be required for Cloudflare success.
- Do not create paid resources.

---

### Task 1: Add regression contract

**Files:**
- Modify: `tests/test_openclaw_cloudflare_primary.py`

- [ ] Add a test asserting the finalizer unit does not contain `Requires=openclaw-gateway.service` or `After=... openclaw-gateway.service`.
- [ ] Assert diagnostic markers exist around daemon-reload, gateway restart, and RPC proof.
- [ ] Run the focused test and confirm RED on current code.

### Task 2: Fix finalizer lifecycle

**Files:**
- Modify: `scripts/openclaw_offline_mount_repair_cloudflare.sh`

- [ ] Remove the hard systemd dependency from the finalizer unit.
- [ ] Keep the finalizer responsible for enabling/restarting the loopback gateway.
- [ ] Add phase markers before and after daemon-reload, gateway restart, and RPC proof.
- [ ] Run the focused test and confirm GREEN.

### Task 3: Verify and recover

- [ ] Run OpenClaw contract tests and CI.
- [ ] Merge only after gates are green.
- [ ] Trigger the existing recovery workflow.
- [ ] Verify local RPC, ready-file creation, Cloudflare Tunnel, Access protection, and public ready URL.
- [ ] Confirm port 18789 remains loopback-only and Tailscale fallback was not damaged.
