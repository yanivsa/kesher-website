# Durable Repo Policy: Kesher Remotion Video Upgrade & Review Policy

This durable repository policy governs all Jules tasks, automated routines, and code changes that modify, render, or evaluate Remotion implementation for the Kesher video pipeline.

---

## 1. Core Product Rule

Remotion must take the **EXISTING NotebookLM MP4** and **UPGRADE** it.

- The NotebookLM video is the single source of truth and **MUST** remain the continuous full-screen/full-frame visual base for **100% of the timeline**.
- Remotion enhances, reframes, and emphasizes the existing source pixels (e.g. through motion plans, spatial saliency tracking, and subtle framing overlays).
- Remotion **MUST NOT** replace the source video with a separate generic visual story, full-screen graphics cards, or synthesized replacement scenes.

---

## 2. Permanent Invariants (Must Preserve Permanently)

1. **Exact NotebookLM Source Audio & Narration**: Always preserve the exact source MP4 audio without alteration or replacement.
2. **Explicit Female Voice Generation Prompt Requirement**: Every NotebookLM generation prompt MUST explicitly include:
   > `השתמש בקול של אישה ישראלית, חם, טבעי, ברור ומקצועי לכל אורך הקריינות.`
3. **Advisory Jules Review**: The automated Jules visual, semantic, and metadata review is advisory only and acts as a quality signal for improvement.
4. **Unconditional YouTube Upload**: Once a technically valid MP4 exists and YouTube OAuth succeeds, the video MUST be uploaded to YouTube unconditionally, regardless of whether Jules review approved, rejected, or was unavailable.

---

## 3. Official Remotion Agent Skills Alignment & Routing

Any AI agent working on Remotion implementation or evaluating Remotion code in this repo SHOULD use the official Remotion Agent Skills when available, adhering strictly to the following routing:

- **`remotion-best-practices`**: Consult first when unsure about Remotion design patterns or overall project setup.
- **`remotion-markup`**: Use for animation, layout, media element usage, and timing constructs.
- **`remotion-docs`**: Use before relying on uncertain, legacy, or newly updated Remotion APIs.
- **`remotion-render`**: Use for render configuration and render pipeline validation.
- **`remotion-multimedia`**: Use for media metadata inspection when useful.
- **`remotion-studio`**: Use for preview setup and interactive studio inspection where practical.

### 🚫 FORBIDDEN SKILL / CAPTIONS RESTRICTION
**DO NOT use `remotion-captions` for this Kesher pipeline.**
The user explicitly does not want Remotion to deal with captions or subtitles.
- Do NOT add burned-in subtitles, caption tracks, karaoke text, or transcript-driven text overlays in Remotion.
- Text overlays in Remotion are restricted to subtle peripheral branding (e.g. `kesher.saharoni.com`) and optional article title badges.

---

## 4. Source-Video-First Remotion Policy

When designing or modifying Remotion compositions, motion plans, or visual overlays for Kesher:

1. **100% Visual Continuity**: The NotebookLM MP4 stays visible as the continuous full-screen/full-frame base for the entire video duration.
2. **No Replacement Audio or TTS**: Never synthesize replacement TTS. Use the exact source MP4 audio.
3. **No Replacement Visual Scenes**: Never create generic full-screen scenes that obscure or replace NotebookLM visuals.
4. **No Hard-Coded Semantic Visual Categories**: Never hard-code visual categories or semantic themes (e.g. couple, parent, child, card, phone, bill) merely because of the article topic.
5. **No Invented Stock/Decorative Objects**: Never invent decorative stock icons, floating symbols, or generic visual overlays merely to make the video look busier.
6. **Source-Derived Motion**: Motion targets MUST be derived directly from the actual current source video: decoded frames, scene change deltas, spatial edge saliency centers, and pixel evidence.
7. **Editorial Pacing over Constant Motion**: Prefer editorial pacing with purposeful push-in, reframe, pan, or spring emphasis around meaningful visual changes, followed by visual rest. Avoid continuous arbitrary zooming and repetitive template motion.
8. **Restrained, Peripheral Overlays**: Overlays MUST remain subtle, restrained, and peripheral. Do not cover the main storytelling area (the central ~70% of the frame).
9. **Source-Specific Feel**: Motion timing, target regions, and emphasis should come from that specific video's own frames and motion plan rather than feeling mass-produced.
10. **No Visual SEO Clutter**: SEO belongs in YouTube metadata (title, description, tags), NOT in Remotion visual clutter. Do not add SEO text overlays inside the video.

---

## 5. Remotion Implementation Best Practices

When writing or editing Remotion code in `src/remotion/`:

- **Frame-Driven Animations**: All motion animations MUST be frame-driven using `useCurrentFrame()`, `interpolate()`, and `spring()` or `Easing` functions.
- **No CSS/Tailwind Motion**: DO NOT use CSS transitions, CSS animations, or Tailwind animation classes for rendered video motion.
- **Media Component Usage**: Use `<Video>` from `@remotion/media` to render the source video stream cleanly.
- **API Verification**: Check official docs/skills before changing Remotion API calls.
- **Compatibility First**: Do not blindly rewrite working Remotion code; verify compatibility and rendered video output.
