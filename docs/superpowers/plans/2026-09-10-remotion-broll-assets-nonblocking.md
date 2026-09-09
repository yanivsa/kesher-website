# Remotion B-roll & Assets Non-Blocking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow Remotion to enrich both Overview and Short with optional B-roll/assets/motion graphics while guaranteeing that missing enrichment can never block publication.

**Architecture:** Keep the existing V5 production / V6 shadow controller identities unchanged. The canonical A+B+C delivery contract remains authoritative; enrichment is an optional post-source visual layer. Jules receives one durable policy covering separate 16:9 Overview and 9:16 Short edit plans, with graceful fallback to source-video motion when assets are absent.

**Tech Stack:** Python controller guard, GitHub Actions, Remotion/React, Jules durable prompt.

**Spec:** `.github/prompts/jules-remotion-video-upgrade.md`

## Global Constraints

- Do not rename the V5/V6 pipeline.
- Preserve the exact NotebookLM source narration/audio.
- Overview and Short remain separately generated authoritative NotebookLM products.
- B-roll/assets/motion graphics are desirable but optional and never a publication gate.
- Untrusted/unlicensed assets are skipped rather than blocking delivery.
- Preserve the canonical A+B+C public completion contract and duplicate-safe publication rules.

---

### Task 1: Lock the non-blocking delivery contract

**Files:**
- Create: `tests/test_kesher_optional_video_enrichment.py`
- Modify: `scripts/kesher_e2e_delivery_guard.py`

- [ ] Add a regression test proving a fully valid A+B+C cycle is complete with no B-roll/assets.
- [ ] Require the serialized delivery report to state `enhancement_required_for_publication: false`.
- [ ] Run the focused unittest and verify it passes.

### Task 2: Replace the restrictive Jules Remotion policy

**Files:**
- Modify: `.github/prompts/jules-remotion-video-upgrade.md`

- [ ] Remove the 100%-source-visual and no-B-roll/no-object restrictions.
- [ ] Define a shared optional enrichment layer with separate Overview and Short profiles.
- [ ] Require per-video `edit-plan.json`, asset provenance, graceful fallback, and After-Effects-style motion graphics implemented in Remotion.
- [ ] State explicitly that missing/unavailable B-roll/assets never blocks render, upload, or Controller completion.

### Task 3: Wire regression coverage into both video PR gates

**Files:**
- Modify: `.github/workflows/kesher-daily-video.yml`
- Modify: `.github/workflows/kesher-short-v4.yml`
- Modify: `.github/workflows/kesher-content-controller-v6.yml`

- [ ] Add the regression test path to PR triggers.
- [ ] Run the optional-enrichment regression in Overview, Short, and V6 shadow validation jobs.
- [ ] Open a focused PR and verify all relevant checks are green before merge.
