# KESHER — autonomous end-to-end delivery and durable waiting (operating contract)

Status: **design / readiness gate; not a production activation**. Scope: existing `yanivsa/kesher-website` workflows and controller state, not a second project, extra ChatGPT scheduled task, or a replacement content system.

## Verified operational diagnosis — 2026-11-14

* Cloudflare Worker `kesher-heartbeat` has one `*/5 * * * *` Cron Trigger and its `WORKFLOW_FILE` binding is `kesher-content-controller.yml`.
* GitHub Actions workflow `Kesher Content Controller` is `disabled_manually` (GitHub workflow ID 337960554). The heartbeat therefore targets a **disabled** dispatch endpoint; a failed/uncertain dispatch is **not** evidence that the controller ran.
* The legacy `automation-state` branch's `.kesher-controller/state.json` was still Schema 5 and last updated 2026-11-08T20:50:56Z when inspected. This **does not prove** a Schema-6 production handover was completed.
* `kesher-content-controller-v6.yml` is **Shadow**; `scripts/kesher_content_controller_v6_runtime.py` explicitly disallows production dispatch. The old `kesher-master-supervisor.yml` runtime job is deliberately retired.
* Existing code already contains bounded recovery primitives: `scripts/kesher_runtime/controller.py`, `policy.py`, `outbox.py`, `media_worker.py`, `output_artifacts.py`. Reuse these; do not create a rival state machine.

**Immediate safety rule:** Do not re-enable the disabled Schema-5 controller, mutate the Cloudflare heartbeat target, turn V6 Shadow into production, or manually dispatch media workers until independent handover/authority evidence proves exactly one live owner. No schema, voice, identity, authorization, or YouTube publication gate may be bypassed.

## Single owner and wake-up path

1. A **single canonical controller**, once the explicit Schema-6 handover is verified, owns state and every dispatch decision. It must use the existing persistent CAS state and the independent authority fence (`require_live` + Cloudflare gateway); never an env-only "live" flag.
2. Use the **existing** Cloudflare 5-minute heartbeat as the sole clock after safely retargeting it to the authorized canonical controller's allowed `workflow_dispatch` entry point. Keep GitHub Actions as the actual execution/review engine. Do **not** add a competing cron or ChatGPT task.
3. A worker's `waiting` receipt is a **terminal result for that short GitHub Actions attempt**, not failure and not permission for new generation. Persist provider task IDs, exact source, attempts and `next_check_at` before it exits. The next authorized heartbeat checks whether it is due and reconciles that exact task.
4. `workflow_run: completed` (if added inside the sole controller) may speed up a wake, but must be treated as a **hint**. Cron remains the recovery fallback for missed notifications. GitHub schedules may be delayed; no correctness requirement may depend on a precise 5-minute wake.
5. Exactly one active command per source/kind/attempt, protected by CAS and GitHub concurrency. Observation errors, unknown GitHub run states, uncertain provider creation or upload, and incomplete pagination **fail closed** instead of triggering a duplicate.
6. Do not use long-running `sleep` loops inside GitHub Actions merely to wait for NotebookLM or YouTube. Persist progress and exit; resume in a later run.

## Source and deliverables contract

Identity for each media artifact: `publication_slot + article_slug + article_content_sha256 + media_kind + exact_item_id + provider_task/artifact_id + bounded_attempt`.

Sequential release gates:

1. **Article:** exact approved source and image, public article URL, actual HTTP 200, article content/source SHA match. Reject wrong or unlicensed imagery.
2. **NotebookLM Overview:** source-locked generation of **16:9** long-form, single authorized task. Persist NotebookLM notebook/source/task/artifact identifiers before polling. Check exact source SHA, Israeli Hebrew female voice throughout, visuals, source provenance, technical hashes, signature and editorial QA. Never publish a male/uncertain-voice attempt. For a rejected item, use bounded new attempt under the same immutable article identity, not a new parallel request.
3. **YouTube Long:** upload only the exact approved MP4 once. First reconcile an existing YouTube ID / uncertain upload, then independently verify public availability, intended metadata and canonical URL.
4. **NotebookLM Short:** only after an independently verified public Long. Create or **resume the existing independent** provider-native 9:16 item. Bind `derive_slug`, `derive_content_sha256`, and the **actual winning `derive_long_item_id` from authoritative Overview output**. Never reuse Long provider media/voice or generate a duplicate Short. Native 720×1280 and 1080×1920 are allowed solely when the same technical, source, audio, video and identity contracts verify the native result; other modes keep their own exact geometry rules.
5. **YouTube Short:** QA and upload only the existing exact approved Short, with the same source, voice, image, signature and YouTube public checks. A technical `pending_review` state is not published and does not imply editorial approval.
6. **Website:** update `src/data/articleVideos.json` via verified PR, pass exact-head CI + Stability + V6 as applicable, deploy via existing Cloudflare workflow, then independently verify that the live article embeds the correct public Long and Short.
7. **DONE:** only after the public article, Long, Short and live embed are independently verified. Record exact URLs, item IDs, source SHA, run IDs, times and verification receipts. Report a complete bundle together; never fabricate YouTube IDs or links.

The existing five parenting-coordination articles form a **bounded backlog**. Process one Long at a time and one Short at a time, prioritizing the daily article's missing Short. Do not block the queue with a completed or superseded item.

## Durable waiting and recovery

| Condition | Next action | Safe limit |
| --- | --- | --- |
| NotebookLM generating / processing | `WAITING_PROVIDER`; poll exact task with read-only API | Wait with staged 5/15/30-minute checks; escalate after a configured deadline; no fresh generation |
| YouTube processing | `WAITING_PUBLIC`; verify existing YouTube ID | Poll existing ID; never upload a second copy |
| Worker dispatch uncertain | Reconcile GitHub run + CAS claim | Re-dispatch **same command ID** only under `outbox.py` bounded rules |
| Recoverable API/transport failure | Retry the exact side-effect-safe read/reconcile operation | Existing `policy.py` bounded attempts; respect provider retry-after |
| Voice/visual/source QA rejection | Quarantine exact bytes; bounded **new attempt** only through policy | Never reinterpret a failed QA check as success |
| Missing OWNER approval / permission / 2FA / expired auth | `BLOCKED_OWNER` with evidence and minimal precise ask | No upload; no synthetic proof, permission bypass or token export |
| Publishing/metadata mismatch | Reconcile existing publication and repair metadata if policy allows | Verify public result before marking complete |
| Failed CI or changed PR head | Stop merge/deploy and revalidate exact new head | CI, Stability, V6 gates all on same SHA |

A pending/waiting receipt does not consume a generation attempt. Only an actual provider creation attempt does. Use state transitions `REQUESTED → ACCEPTED → STARTED → MEANINGFUL_PROGRESS → OUTPUT_CREATED → TECHNICALLY_VALIDATED → UPLOAD_STARTED → UPLOADED → PROCESSED → PUBLISHED → PUBLICLY_VERIFIED` where applicable; track `WAITING_PROVIDER`, `WAITING_PUBLIC`, `BLOCKED_OWNER` as **operational substatuses**, not unauthorized new canonical phases.

## Fo / Pally browser fallback

**Not the scheduler or production state owner.** Route a bounded task to one agent **only if** the supported NotebookLM path is unavailable due to an interactive browser/2FA/authentication challenge that cannot be solved within the approved interface. Require:

* One agent (Fo **or** Pally), one clear immutable request (slug/SHA/item ID and evidence-only task), and a single ACK.
* The agent may inspect a browser and return non-secret evidence or ask the owner to sign in; it must **not** independently create an untracked provider task, modify canonical state, or publish to YouTube.
* Never paste passwords, cookies, refresh tokens or credentials into chat, issue logs or GitHub artifacts; authorization stays with the already-approved provider flow.
* If a browser-assisted action modifies provider state, the canonical controller must first independently reconcile exact provider/source identity before proceeding.

## Activation plan — no shortcut

1. Audit the existing Cloudflare heartbeat target, disabled controller, Schema-5 state, GitHub active/queued workers, and Schema-6 handover journal. Identify a *single* authoritative production state. If ambiguous, stop.
2. Complete **approved** Schema-6 cutover via `kesher-production-cutover.yml` and independent gateway attestations; do not reactivate legacy workers by removing guards.
3. Add/enable a single trusted canonical `workflow_dispatch` controller entry; verify it observes state, performs a CAS decision and delivers **one** exact command. Verify independent gateway admission, not just GitHub token access.
4. Retarget **existing** `kesher-heartbeat` only after step 3. Add a fail-closed heartbeat health check for disabled workflow, permission errors and a missing run acceptance receipt. No second scheduler.
5. Dry-run a `WAITING_PROVIDER` cycle and verify that the first run exits, the next due wake resumes the **same** task, a duplicate wake is a no-op, and a time-out produces a single precise blocker.
6. Verify end-to-end test with one non-sensitive item, including real public YouTube metadata, article embed and public Cloudflare deployment. Only then consider the pipeline production-autonomous.

## Evidence / acceptance checks

- [ ] One verified authoritative controller and one state writer; Schema 6 + gateway fence independently active
- [ ] Existing 5-minute Cloudflare heartbeat points only to **enabled and authorized** controller
- [ ] Heartbeat log shows accepted controller run, not merely HTTP 204 or a disabled-workflow 422
- [ ] Provider pending survives worker exit and resumes **same** task ID after wake
- [ ] Duplicate cron, `workflow_run` or manual wake produces **zero extra generations/uploads**
- [ ] Short is provider-native 9:16, source- and Long-bound, and voice/QA verified
- [ ] GitHub CI + Stability + V6 exact-head checks pass for changed code/policy
- [ ] YouTube Long + Short both independently public; article embeds and links verified
- [ ] Daily bundle completes automatically; unanswered block escalates with exact evidence
- [ ] Existing five-article backlog drains without media-type overlap
- [ ] No newly created ChatGPT schedule, Rube dependency, or unreviewed Fo/Pally browser automation

**Do not mark this plan implemented or production-healthy merely because this document is merged.** It is the execution/QA contract; activation requires the independently verified steps above.
