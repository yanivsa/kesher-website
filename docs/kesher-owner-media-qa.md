# KESHER OWNER-only immutable media quality release gate

This gate runs **inside the existing canonical GitHub media worker**, immediately
before any first YouTube upload. It creates no workflow, agent, paid-service
dependency, generation, or upload. Previously uploaded YouTube resources remain
on their existing read-only reconciliation path.

## Why

Technical rendering, FFmpeg/ffprobe, valid ASR output, a green GitHub Action and
the presence of a contact sheet are **not** a visual or scientific QA PASS.
The prior worker advanced pending media to `approved` without consulting an
OWNER editorial certificate. This gate refuses to infer editorial approval.

## OWNER review and approval

1. Reconcile the approved user-supplied topic and current
   `source_slug`/`content_sha256` in Issue #1210. Never invent a topic.
2. Reuse the canonical command and its **already archived** output; do not
   run another generator or upload. Examine the actual final video, all eight
   frames **and motion**, original source-audio and the existing Hebrew
   transcript. FFmpeg and built-in Whisper suffice for technical audio and
   transcription; Descript is *not* required. Transcription alone does not
   prove subjective audio clarity. If direct audio audition was not done,
   record the authorized audio analysis method accurately.
3. Compare **spoken claims** against the actual cited science; reject
   exaggerated prevalence, effects or universality. Check H1/title/YouTube
   description and the exact article URL. Review visual continuity, RTL,
   overlap, text density and topic-specific photorealistic scenes. Neither a
   successful render nor eight arbitrary frames proves aesthetic quality.
4. Confirm commercial rights of the **exact** voice and visible imagery.
   Record authoritative HTTPS license evidence, not just a claim about
   a provider's similarly named product.
5. ONLY after independent genuine QA, make a reviewed PR adding
   `research/owner-media-quality/<source_slug>--<overview|short>.json`,
   bound to the immutable canonical **item ID**, published article source
   SHA, final MP4 hash, manifest hash, transcript hash, source-file hash,
   contact sheet and eight frame hashes. This JSON must include:
   `schema_version=1`, `reviewed_by="OWNER"`, a real `reviewed_at`,
   five `checks` (visual/semantic/audio/metadata/licensing)=`approved`,
   `methods.visual="full_motion_and_frames"`,
   `methods.semantic="research_vs_exact_transcript"` and
   `methods.audio` either `direct_playback` or
   `authorized_audio_tool_with_script_comparison`, Hebrew review notes,
   `rights.commercial_use_permitted=true` and authoritative HTTPS URLs for
   `rights.voice_license_url` and `rights.visual_license_url`.
   Never write a fictitious passing certificate or reuse an old file/hash.
6. Merge only with green exact-head CI and normal source/authority safeguards.
   On a subsequent authorized canonical publish, the gate reads that exact
   merged approval and compares **every** identity and evidence hash before
   permitting the existing GitHub OAuth upload. Existing channel and
   archive dedup safeguards remain active.
7. If evidence is pending, mismatched, unlicensed, slide-heavy or scientifically
   misleading, keep `QUALITY_HOLD` or `QA_PENDING`; do not write PASS
   or upload. Surface the specific blocker in Issue #1210.

**Important:** This is a conservative publication safeguard, not a magic
computer-vision judge. A passing certificate requires an actual OWNER quality
review; missing footage, missing voice rights, or an unscripted provider's
unsupported claims cannot be made valid by a green technical test. Only
topics Yaniv approved may enter this process. No Jules, retired workflow,
Make or direct Composio YouTube upload.

## Existing Vantage Overview

The currently public 2026-11-09 Overview remains PUBLISHED /
QUALITY_HOLD due to an actual scientific/visual defect. Its YouTube
description carries an evidence-based caveat. This code does not alter
an uploaded video, create a replacement link or count the assisted cycle
toward the 3/3 autonomous target.
