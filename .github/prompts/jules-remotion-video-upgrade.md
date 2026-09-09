# Durable Repo Policy: Kesher Remotion Video Upgrade & Review Policy

Policy-Version: 2

This durable repository policy governs Jules tasks, automated routines, and code changes that modify, render, or evaluate Remotion implementation for the Kesher video pipeline.

**Pipeline identity is unchanged:** V5 remains the production controller and V6 remains the shadow/evolution path unless separately promoted. This policy version is not a new pipeline version.

---

## 1. Core Product Rule

Remotion upgrades the **existing authoritative NotebookLM MP4** for each product.

- Video Overview and Short remain **separately generated NotebookLM products**. Never derive the Short by cutting the Overview unless the canonical production contract is deliberately changed in a separate reviewed change.
- The exact accepted NotebookLM narration/audio for each product remains authoritative and MUST be preserved without replacement TTS.
- Remotion MAY enhance the picture with relevant B-roll, sourced visual assets, source-derived reframing, transitions, compositing, masks, parallax, zoom/pan, depth treatments, restrained text/branding, and After-Effects-style motion graphics implemented in Remotion.
- B-roll/assets MAY temporarily occupy the full frame when editorially appropriate. The old requirement that NotebookLM source pixels remain visible for 100% of the timeline is removed.
- Remotion must never fabricate factual visual evidence, imply that a stock/generated person is a real client, or use visuals that contradict the narration/article.

---

## 2. Permanent Publication Invariants

1. **Exact NotebookLM Source Audio & Narration**: Preserve the exact accepted source MP4 narration/audio. Do not synthesize replacement TTS.
2. **Female-first voice generation and bounded fallback — Video Overview and Short**: Every NotebookLM generation prompt for both products MUST explicitly request a female Israeli voice:
   > `השתמש בקול של אישה ישראלית, חם, טבעי, ברור ומקצועי לכל אורך הקריינות.`

   The voice rule is bounded and identical for both products:
   - Attempts 1 and 2: a detected male voice must not be published; regenerate the same authoritative source identity while preserving the female-voice request.
   - Attempt 3: still request a female voice. If the third accepted candidate is nevertheless detected as male, male voice is an allowed fallback when all other gates pass.
   - An accepted third-attempt male fallback MUST NOT trigger a fourth generation solely because of voice gender.
   - Voice fallback never relaxes source identity, duplicate prevention, aspect ratio, audio, duration, metadata, publication, or other technical gates.
3. **Jules review is strict and advisory**: Jules SHOULD evaluate visual, semantic and metadata quality honestly. Rejection, timeout, reviewer unavailability, malformed review, insufficient B-roll, insufficient assets, or skipped enrichment MUST NOT by itself block upload when the canonical technical publication gate passes.
4. **Technical publication authority**: Upload permission comes only from the canonical Kesher production contract and technical gate. Source identity, final MP4 SHA-256, manifest/evidence identity, metadata validity and duplicate-safe YouTube reconciliation remain fail-closed.
5. **Exact-evidence identity**: A structured Jules review must refer to the exact item/final MP4/manifest/transcript/source/frame evidence it inspected. A review identity mismatch invalidates the review record but does not change the independent technical publication decision.
6. **Daily automation**: Preserve scheduled/controller-driven GitHub Actions and durable resume behavior. Do not turn the daily pipeline into a manual-only flow.
7. **A+B+C remains the only completion contract**: Controller completion depends on the canonical public Article + verified public Video Overview + verified public portrait Short (including existing origin/signature/identity gates). **B-roll, external assets, edit-plan richness and motion-graphics richness are never required for Controller completion.**

---

## 3. Non-Blocking Enrichment Contract — MUST NOT STOP PUBLICATION

B-roll/assets/motion graphics are a quality layer, not a reliability gate.

- Prefer useful enrichment when relevant assets can be obtained safely and efficiently.
- If no suitable B-roll or asset is available, continue with the authoritative NotebookLM video plus source-derived Remotion motion/reframing/branding as the fallback.
- If asset retrieval, generation, download, validation, provenance, decoding or rendering of a particular optional asset fails, **skip that asset and continue**. Do not fail the Controller solely because an optional enrichment asset is missing.
- Never regenerate the NotebookLM source solely because B-roll/assets are unavailable.
- Never create a duplicate video generation or duplicate YouTube upload to chase richer B-roll/assets.
- Do not impose a minimum B-roll count, minimum asset count or percentage-of-timeline quota as a publication condition.
- An optional enrichment failure may be recorded as a quality/advisory signal for future improvement, but it MUST NOT keep an otherwise valid A+B+C cycle open.
- Unlicensed, unverifiable, corrupted or semantically unsafe assets are skipped rather than used and rather than blocking delivery.

The Controller's durable delivery report MUST make this explicit with:

`enhancement_required_for_publication: false`

---

## 4. Shared Remotion Enhancement Layer, Separate Product Profiles

Use one reusable Remotion enhancement architecture where practical, but build an independent edit plan for each product.

### Video Overview — landscape 16:9

- Preserve the Overview's own NotebookLM audio and source identity.
- Use an editorial pace appropriate to longer viewing: purposeful B-roll, photos/assets, push-ins, reframes, pans, parallax, masks, transitions, picture-in-picture or full-screen B-roll, and restrained lower-thirds/branding where useful.
- Allow visual rest. Do not force constant motion or a new asset every few seconds.
- B-roll should support the point currently being narrated rather than act as generic decoration.

### Short — portrait 9:16

- Preserve the Short's own independently generated NotebookLM audio/source identity and canonical portrait/origin rules.
- Target technical portrait output according to the production contract (currently 1080x1920 where required by the canonical gate).
- Use a faster editorial rhythm: stronger opening visual hook, punch-ins, quick source-aware reframing, relevant short B-roll inserts/assets, kinetic compositing and concise motion-graphics emphasis.
- Do not turn the Short into a crop of the Overview and do not substitute Overview provider identity for the Short.
- If enrichment is unavailable, a clean portrait source-based Remotion treatment remains valid if all canonical technical gates pass.

---

## 5. Per-Video `edit-plan.json`

For both Overview and Short, the enhancement implementation SHOULD produce or materialize a deterministic per-item `edit-plan.json` (or equivalent durable structured plan) tied to the exact source identity.

The plan should record enough information to reproduce/inspect the edit, for example:

- product: `overview` or `short`
- authoritative item/source identifiers and SHA-256 values
- aspect ratio / output dimensions
- timeline segments with start/end timing
- visual action type such as source, reframe, b-roll, asset, motion-graphic, transition
- asset reference when used
- editorial purpose / narration cue
- provenance/licensing metadata for external assets when applicable
- fallback outcome when an optional asset was skipped

The plan is an editing aid and quality artifact. Missing optional B-roll entries MUST NOT make the plan or publication invalid.

---

## 6. Asset & B-roll Rules

Permitted sources include source-derived visuals, repository-owned/user-owned assets, appropriately licensed/free-to-use assets, and generated assets when the applicable service/license allows their use.

- Record provenance for external assets when practical and required by the asset source.
- Never use an asset when licensing/provenance is materially uncertain; skip it instead.
- Never depict a stock/generated person as Shira, a real client, or a real case unless that identity is actually established and authorized.
- Do not hard-code topic clichés (couple arguing, phone, bills, child, etc.) merely to make every video visually busy. Choose assets because they fit the actual narration/edit plan.
- Reuse shared transition/compositing primitives, but avoid making every video feel like the same template.
- Asset sourcing must be idempotent and duplicate-safe where it creates durable artifacts.

---

## 7. Official Remotion Agent Skills Alignment & Routing

Agents working on Remotion SHOULD use the official Remotion Agent Skills when available:

- `remotion-best-practices`: overall setup/design patterns.
- `remotion-markup`: animation, layout, sequences, media, transitions and timing.
- `remotion-docs`: verify uncertain/current APIs.
- `remotion-render`: render configuration and validation.
- `remotion-multimedia`: media metadata/processing when useful.
- `remotion-studio`: preview/inspection when practical.
- `remotion-upgrade`: only for a deliberate isolated dependency upgrade; never auto-upgrade Remotion/Mediabunny/skills during the normal daily run.

### Captions restriction

**Do not use `remotion-captions` for this Kesher pipeline.**

- Do not add transcript-driven burned-in subtitles, karaoke captions or Remotion-generated caption tracks.
- Text already baked into NotebookLM pixels remains part of the source and is allowed.
- Remotion may add restrained non-caption editorial text such as peripheral branding, a title badge, a concise lower-third or motion-graphic label when it supports the edit and does not become subtitle-like transcript repetition.

---

## 8. After-Effects-Style Motion Design in Remotion

"After Effects" in this policy means **After-Effects-style visual treatment implemented with Remotion/React**, not a dependency on Adobe After Effects.

Useful techniques include:

- layered compositing and masking
- animated crop/reframe and camera-like push/pan
- parallax/depth treatment
- reveals/wipes/mattes
- spring/easing-driven object/text motion
- picture-in-picture or split layouts
- image/video B-roll timing
- subtle blur/scale/opacity/transform emphasis
- reusable branded motion primitives

Use these to improve storytelling, not simply to maximize animation density.

---

## 9. Remotion Implementation Best Practices

When editing `src/remotion/`:

- All rendered motion must be frame-driven with Remotion timing (`useCurrentFrame()`, `interpolate()`, `spring()`, `Easing`, sequences/transitions as appropriate).
- Do not rely on CSS transitions, CSS animations or Tailwind animation classes for deterministic rendered video motion.
- Preserve exact accepted source audio even when B-roll or full-screen assets temporarily replace source pixels.
- Keep output deterministic from source identity + edit plan + referenced assets.
- Validate media compatibility/dimensions before using an optional asset; skip invalid optional assets rather than blocking the canonical delivery.
- Check official docs/skills before relying on uncertain or newly changed Remotion APIs.
- Do not blindly rewrite working Remotion code or auto-upgrade dependencies in unrelated changes.

---

## 10. Review & Acceptance

Jules visual review SHOULD flag low-quality outcomes such as excessive slide/card-like visuals, text-heavy layouts, repetitive generic stock, unrelated B-roll, misleading imagery, bad pacing or mechanical template motion.

However, the review remains advisory relative to publication. A technically valid exact-source Overview/Short may publish even when optional visual enrichment is sparse or absent.

**Never block publication solely because:**
- no B-roll was found,
- no external assets were found,
- optional asset generation/download failed,
- the edit plan used only source-derived motion,
- an advisory reviewer wanted richer visuals.

Quality findings should feed a later non-duplicating improvement task rather than hold the daily A+B+C delivery hostage.
