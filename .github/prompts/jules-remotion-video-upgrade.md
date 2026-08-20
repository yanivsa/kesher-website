# Durable Repo Policy: Kesher Remotion Video Upgrade & Review Policy

Policy-Version: 1

This durable repository policy governs all Jules tasks, automated routines, and code changes that modify, render, or evaluate Remotion implementation for the Kesher video pipeline.

---

## 1. Core Product Rule

Remotion must take the **EXISTING NotebookLM MP4** and **UPGRADE** it.

- The NotebookLM video is the single source of truth and **MUST** remain the continuous full-screen/full-frame visual base for **100% of the timeline**.
- Remotion enhances, reframes, and emphasizes the existing source pixels through source-derived motion plans, scene changes, spatial saliency/high-contrast regions, and restrained framing overlays.
- Remotion **MUST NOT** replace the source video with a separate generic visual story, full-screen graphics cards, synthesized replacement scenes, or invented decorative objects.

---

## 2. Permanent Invariants (Must Preserve Permanently)

1. **Exact NotebookLM Source Audio & Narration**: Always preserve the exact source MP4 audio without alteration or replacement.
2. **Explicit Female Voice Generation Prompt Requirement**: Every NotebookLM generation prompt MUST explicitly include:
   > `השתמש בקול של אישה ישראלית, חם, טבעי, ברור ומקצועי לכל אורך הקריינות.`
3. **Strict visual review language for slide/card-like output**: The automated Jules visual review MUST report as rejected any video that is composed of slide/card-like, text-heavy, timeline/diagram, repeated-frame, or generic illustrative visuals.
4. **Jules review is a mandatory publication gate**: A technically valid MP4 MUST NOT be uploaded to YouTube until Jules has completed a structured review of the immutable evidence for that exact MP4 and returned `approved` for visual, semantic and metadata gates. Reviewer timeout, unavailability, malformed output or a rejected decision MUST block upload while preserving the exact video/evidence for controller-managed retry or repair. Never bypass Jules to preserve schedule timing.
5. **Exact-evidence identity**: The approval MUST refer to the same item ID, final MP4 SHA-256, manifest SHA-256, transcript SHA-256, source SHA-256 and frame hashes that are later presented to the upload step. Any mismatch invalidates the approval.
6. **Daily Automation**: Changes to review policy or Remotion implementation MUST preserve the scheduled controller-driven daily GitHub Actions pipeline and its durable resume behavior. Do not turn the daily flow into a manual-only process.

---

## 3. Official Remotion Agent Skills Alignment & Routing

Any AI agent working on Remotion implementation or evaluating Remotion code in this repo SHOULD use the official Remotion Agent Skills when available, adhering strictly to the following routing:

- **`remotion-best-practices`**: Consult first when unsure about Remotion design patterns or overall project setup.
- **`remotion-markup`**: Use for animation, layout, media element usage, and timing constructs.
- **`remotion-docs`**: Use before relying on uncertain, legacy, or newly updated Remotion APIs.
- **`remotion-render`**: Use for render configuration and render pipeline validation.
- **`remotion-multimedia`**: Use for media metadata inspection when useful.
- **`remotion-studio`**: Use for preview setup and interactive studio inspection where practical.
- **`remotion-upgrade`**: Maintenance-only guidance for a deliberate future Remotion/Mediabunny/Agent Skills upgrade. Never auto-upgrade Remotion, Mediabunny, or Agent Skills as part of the normal daily video run or an unrelated review PR. Any upgrade must be isolated, compatibility-checked, rendered, tested, and reviewed before production adoption.

### 🚫 FORBIDDEN SKILL / CAPTIONS RESTRICTION

**DO NOT use `remotion-captions` for this Kesher pipeline.**

The restriction applies to captions/subtitles **created, generated, transformed, or edited by Remotion**.

- Do NOT add burned-in subtitles, caption tracks, karaoke text, or transcript-driven text overlays in Remotion.
- Text that already exists inside the pixels of the NotebookLM source MP4 is part of the immutable source video. It is allowed and MUST NOT be treated as a Remotion-generated caption violation merely because it is visible in sampled frames.
- Remotion must not rewrite, remove, translate, restyle, or otherwise alter text that is already baked into NotebookLM source pixels.
- New Remotion text overlays are restricted to subtle peripheral branding (for example `kesher.saharoni.com`) and optional restrained article-title badges.

---

## 4. Source-Video-First Remotion Policy

When designing or modifying Remotion compositions, motion plans, or visual overlays for Kesher:

1. **100% Visual Continuity**: The NotebookLM MP4 stays visible as the continuous full-screen/full-frame base for the entire video duration.
2. **No Replacement Audio or TTS**: Never synthesize replacement TTS. Use the exact source MP4 audio.
3. **No Replacement Visual Scenes**: Never create generic full-screen scenes that obscure or replace NotebookLM visuals.
4. **No Hard-Coded Semantic Visual Categories**: Never hard-code visual categories or semantic themes (for example couple, parent, child, card, phone, bill) merely because of the article topic.
5. **No Invented Stock/Decorative Objects**: Never invent decorative stock icons or floating objects (for example phones, bills, keys, people, toys, message bubbles) just to make the video look busier.
6. **Source-Derived Motion**: Motion targets MUST be derived directly from the actual current source video: decoded frames, scene-change deltas, spatial edge saliency/high-contrast centers, and the generated motion plan.
7. **Editorial Pacing over Constant Motion**: Prefer purposeful push-in, reframe, pan, or spring emphasis around meaningful visual changes, followed by visual rest. Avoid continuous arbitrary zooming and repetitive template motion.
8. **Restrained, Peripheral Overlays**: Overlays MUST remain subtle, restrained, and peripheral. Do not cover the main storytelling area (the central ~70% of the frame).
9. **Source-Specific Feel**: Motion timing, target regions, and emphasis should come from that specific video's own frames and motion plan rather than feeling mass-produced.
10. **No Visual SEO Clutter**: SEO belongs in YouTube metadata (title, description, tags), NOT in Remotion visual clutter. Do not add SEO text overlays inside the video.

---

## 5. Remotion Implementation Best Practices

When writing or editing Remotion code in `src/remotion/`:

- **Frame-Driven Animations**: All rendered motion MUST be frame-driven using `useCurrentFrame()`, `interpolate()`, `spring()`, or `Easing` functions.
- **No CSS/Tailwind Motion**: DO NOT use CSS transitions, CSS animations, or Tailwind animation classes for rendered video motion.
- **Media Component Usage**: Use the project-compatible Remotion media component for the source stream and preserve the source audio contract.
- **API Verification**: Check official docs/skills before changing Remotion API calls.
- **Compatibility First**: Do not blindly rewrite working Remotion code; verify compatibility and rendered video output.
