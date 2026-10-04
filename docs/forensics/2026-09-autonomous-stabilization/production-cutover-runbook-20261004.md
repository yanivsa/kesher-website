# Schema-6 production cutover implementation and blocked administrator handoff

**NO SCHEMA-6 PRODUCTION ACTIVATION HAS OCCURRED.** No live workflow disable,
credential revocation, automation-state write, handover, generation, upload,
deployment or production dispatch was performed in this implementation task.

Base main: `5fc62bce0df27a3ff02ab81d8ce156a23da355ab`. Branch:
`codex/schema6-production-cutover`. The implementation is reviewable in a Draft
PR; live cutover remains **BLOCKED** until the prerequisites below are actually
implemented and independently proven at the protected services. Supplying a
receipt file, environment flag or an adapter that returns configured answers
does not satisfy a prerequisite. `PrerequisitePort` always refuses both methods.

## What the new entrypoint executes

`.github/workflows/kesher-production-cutover.yml` accepts only `epoch` and
`reviewed_revision`. It is manual-only, repository/main bound, has no schedule
or push trigger, uses a protected `kesher-cutover` environment and receives only
read access plus Actions OIDC. Checkout uses the exact invocation revision and
does not persist credentials. The existing production controller stays inert.

`python -m scripts.kesher_runtime.cutover_entry` independently compares checkout,
invocation and fresh main SHAs, obtains a short-lived Actions identity, then
submits exactly one POST to the implemented `/v1/cutover/step` service endpoint.
It does not retry a lost response. A NEW reviewed invocation reconciles the
remote journal; rerunning an old uncertain mutation is forbidden.

`cutover_service` binds loopback behind administrator-managed TLS ingress. It
verifies the OIDC signature, fixed issuer/audience, repository ID, protected
environment, exact main/workflow SHA, manual event and live run/attempt. Reusable
workflow identities are refused. It durably claims the attempt before any
effect. Its persistent SQLite ledger is a replay-denial ledger only, never a
resource fence or alternate canonical state store. Missing/lost storage refuses;
initialization is an exclusive administrator operation, never recovery logic.

`live_cutover.build_runtime` composes the existing GitExclusionEpoch, GithubDrain,
GitHubHandover, GitHubAuthorityObserver, ExclusionFence and Coordinator. Trusted
native observers, registration bindings, migration custody material, sealing
key and independent approval are installed by the service administrator; HTTP
clients cannot supply them. A callable original-input supplier stays attached
to its native transport and recovers the exact original immutable Schema-5 blob
after STATE_IMPORTED. Current Schema-6 state is never remigrated as legacy input.

The credential-owning `GuardedGitHub` admits only the exact original state
blob/tree/parent and atomic no-op-main plus automation-state CAS. It separately
enforces the installed retirement ID/path allowlist when journaling and when
disabling/canceling at the actual endpoint. It denies publication, dispatch,
arbitrary content/ref/tree writes, and protected worker/controller/diagnostic/
infrastructure retirement. Every mutation requires fresh native grant-boundary
and exact-main readback. Its narrow interface cannot revoke a token held outside
the service; a native direct-write-denial boundary is a separate prerequisite.

One invocation performs one resource bootstrap step, one Actions effect with
durable surrounding journal writes, or one Coordinator transition. It first
inspects all six resources and infrastructure separation. Partial exclusion,
unknown sessions, competing ownership or missing observers stops before any
effect. It never generates an article/image/video, uploads or deploys content,
infers public completion or activates the controller.

## Service feasibility and exact remaining prerequisites

| Resource | Delivered implementation | Required service-side proof before live use |
| --- | --- | --- |
| github | AUTOMATED exact registration inventory, native Git CAS, Actions intent/drain, endpoint authorization and restart readback; HUMAN_PREREQUISITE native grant boundary | For `yanivsa/kesher-website`, repository ID `1239881973`, node ID `R_kgDOSecY9Q`: owner-admin complete PAT/OAuth/App/SSH/deploy-key and old workflow-token inventory/retirement, independently enforced denial of direct state/Actions mutation, and isolated gateway App admission. Repository is personal-owned; organization-only PAT administration cannot prove its complete personal grant inventory. |
| jules | HUMAN_PREREQUISITE; unavailable production port refuses | Administrator retires predecessor API keys and repository grants; independently settles every existing session and proves none retains write authority. Install a canonical command gateway and native inventory/epoch/default-deny/readback observer. Deleting a session is not evidence that an already-running operation stopped. |
| notebooklm | HUMAN_PREREQUISITE; unavailable production port refuses | Exact consumer notebook is `e101e7d7-5305-45b3-a611-21a5475ceb63`. Account administrator invalidates predecessor cookies, master tokens and sessions, settles running work and proves the canonical gateway boundary. Enterprise IAM APIs cannot certify this consumer notebook. Missing consumer readback remains BLOCKED. |
| youtube | HUMAN_PREREQUISITE; unavailable production port refuses | Independently bind the exact channel, inventory all predecessor OAuth grants and already-issued resumable capabilities, retire/settle them with native readback. Place distinct canonical credentials from a separate OAuth project behind the command gate; legacy definitions must not inherit them. A refresh-token revoke alone cannot certify outstanding upload capabilities or complete all grants. |
| cloudflare | HUMAN_PREREQUISITE; unavailable production port refuses | Independently bind exact account and Pages project. Account owner inventories members/global keys/user and account API tokens/Pages integrations, revokes predecessor authority, settles deployments and proves isolated canonical scopes/native denial readback. User-token list/delete/verify alone cannot enumerate every other member/integration/global key. |
| image_provider | HUMAN_PREREQUISITE; unavailable production port refuses | Identify every actual provider/project, retire predecessor keys, sessions and issued bearer capabilities, settle generation operations and establish native scoped canonical admission/readback. Deleting a Google service-account key does not invalidate already-issued short-lived tokens. Unknown provider or actor is BLOCKED. |

These five external ports are deliberately unavailable in this PR. Native
service observers/boundaries have not been deployed or proven. Their absence is
an operational blocker, not a waived implementation/validation result. An
administrator must supply real enforcement and reviewable readback adapters;
there is no generic production factory that fabricates them.

Primary API references supporting these limits:
[GitHub rulesets](https://docs.github.com/en/rest/repos/rules),
[GitHub Actions workflow APIs](https://docs.github.com/en/rest/actions/workflows),
[organization PAT administration](https://docs.github.com/en/rest/orgs/personal-access-tokens),
[known credential revocation](https://docs.github.com/en/rest/credentials/revoke),
[Actions OIDC claims](https://docs.github.com/en/actions/reference/security/oidc),
[Jules sessions](https://jules.google/docs/api/reference/sessions),
[Jules authentication](https://jules.google/docs/api/reference/authentication/),
[NotebookLM Enterprise setup](https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/set-up-notebooklm),
[YouTube OAuth revocation](https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps),
[resumable upload protocol](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol),
[Cloudflare user token APIs](https://developers.cloudflare.com/api/resources/user/subresources/tokens/),
[Cloudflare account token APIs](https://developers.cloudflare.com/api/resources/accounts/subresources/tokens/),
[Google key deletion limitations](https://docs.cloud.google.com/iam/docs/keys-create-delete).

## GitHub registrations, infrastructure and the manual bridges

The sanitized baseline contains all **111** exact service registrations: 72
current definitions and 39 retained registrations without current YAML. All 72
existing IDs are pinned. Unknown, missing, duplicate or rebound registrations
refuse. The new cutover workflow brings the expected post-merge inventory to
112; its actual newly assigned ID MUST be independently read and approved,
never guessed. This cannot be completed before the workflow exists on main.

Retirement targets are 36 retired definitions, three bounded manual bridges and
all 39 retained registrations: **78** exact IDs. Two retained system paths are
`dynamic/dependabot/dependabot-updates` (294204178) and
`dynamic/dependabot/update-graph` (320961763); both support active/terminal exact
attempt handling. Arbitrary dynamic paths remain refused. The five canonical
workers, controller, eight diagnostics and 19 infrastructure definitions stay
outside the gateway retirement allowlist.

The drain journals identity/intent before every disable/cancel. It enumerates
queued, in_progress, waiting, pending and requested runs, verifies immutable
run/attempt receipts and requires terminal conclusion readback. Lost cancel
intent is never replayed. Disable reconciliation remains narrowly bounded and
requires fresh desired-state observation. Re-enable, new registration and new
attempt races refuse. Two fresh complete inventories recertify all 78 proved
targets as a batch: 18 global GETs in the two-page 111-registration fixture,
instead of 18 per target. Every known terminal attempt is still reread, every
GET retains fresh epoch checks, and no read is cached across invocations.
Real rate limits, pages and terminal history can add requests; exhaustion or
timeout stops safely and must be read back before a new invocation.

All 19 separate infrastructure definitions remain unchanged. Their actual
resource, credential class and service scope must be independently separated
from ALL six protected resource IDs, exact repo/policy/code/definition/review.
Callbacks cannot select their own trust roots. CI writes statuses in the same
repository; its current token does not prove disjoint repository authority.
The YouTube OAuth diagnostic retains upload/metadata capability on the legacy
channel and cannot be blessed as read-only. OCI/OpenClaw workflows need full
OCI and Cloudflare boundaries for every effective credential; a Cloudflare-only
receipt cannot cover OCI. Missing service mappings/scopes require an explicit
reviewed policy change plus native enforcement, not silent credential removal
or blind retirement. The evidence report lists each exact affected workflow.

The current-main manual daily-video and Short V4 bridges, native portrait and
sharpness fixes, and PR1054 manual deployment implementation remain preserved.
Only inert PR/push triggers were removed to make these bridges manual-only.
Each bridge checks the actual legacy state before obtaining provider credentials
and refuses any exclusion epoch, handover phase or Schema-6 document. Once
exclusion starts, it is unavailable; all three are disabled and drained before
VERIFIED. A legacy checkout that omits this check still requires native service
credential exclusion; the YAML guard is not a fence.

## Post-merge sequence — conditional, separately authorized, NOT executed

1. Merge only after human code review. Read current main again. If it differs
   from the reviewed deployment revision, review/rebind the new exact revision
   and all executable/policy/closed-evidence inputs. Do not reuse this base SHA
   as a future deployment SHA or rely on the Draft PR branch as production code.

2. Collect complete read-only registration evidence and independently bind the
   newly registered cutover ID. Review the exact 112 expected ID/path bindings:

   ```sh
   git fetch origin main
   git rev-parse origin/main
   gh api --paginate repos/yanivsa/kesher-website/actions/workflows?per_page=100 \
     --jq '.workflows[] | {id,path,state}'
   ```

3. Complete every native administrator prerequisite above under separate live
   authorization. Review all 19 infrastructure boundaries and six exact resource
   IDs; retire predecessor grants/sessions/capabilities without revealing their
   contents. Bind the exact code/policy/registration/material/closed-floor/key
   digests and sealing custody. If ANY proof is unavailable, STOP BLOCKED. Do not
   proceed to step 4 or dispatch this workflow using synthetic ports.

4. Install the reviewed repository code on the independent credential-owning
   service. Implement an administrator-owned `trusted_kesher_cutover.build`
   factory that calls `live_cutover.build_runtime` with the actual native ports
   and grant boundary, constructs ActionsIdentity with actual repository ID,
   reviewed main and TLS audience, and returns CutoverApplication. Its
   `review_check` freshly verifies installed executable/policy/evidence bytes.
   This factory and native observers are pending administrator implementation;
   they are deliberately not provided as a pretend service attestation.
   Initialize the durable denial ledger ONCE in protected persistent storage:

   ```sh
   python - <<'PY'
   from scripts.kesher_runtime.cutover_service import InvocationJournal
   InvocationJournal.initialize('/var/lib/kesher-cutover/invocations.sqlite')
   PY
   python -m scripts.kesher_runtime.cutover_service \
     --factory trusted_kesher_cutover:build --port 8789
   ```

   Supply private credentials/keys only through service-side protected custody;
   never repository/Actions variables, client payloads or logs. Configure TLS
   ingress, protected environment reviewers, main-only environment deployment,
   and repository variable `KESHER_CUTOVER_GATEWAY_URL` to its exact HTTPS origin.
   Actions holds no service mutation credential. Do not reinitialize a lost
   invocation ledger; block and reconcile protected storage and remote intents.

5. Independently approve one fixed epoch and current reviewed main revision.
   Execute ONE manual invocation and read its safe phase and exact remote state:

   ```sh
   gh workflow run kesher-production-cutover.yml \
     --repo yanivsa/kesher-website --ref main \
     -f epoch=ADMIN_APPROVED_EPOCH -f reviewed_revision=EXACT_REVIEWED_CURRENT_MAIN_SHA
   gh run list --repo yanivsa/kesher-website \
     --workflow kesher-production-cutover.yml --limit 5
   ```

   The two uppercase values are mandatory administrator-selected bindings,
   not executable default identities. Approve the protected-environment job.
   After each invocation, the trusted observer reads the immutable original
   state ref/blob/journal, six fresh service fences and exact terminal attempts.
   Resolve any BLOCKED/unknown response before invoking again. A new invocation
   reconciles existing intent; never rerun an uncertain provider mutation.

6. Continue the SAME reviewed epoch/revision, one newly authorized invocation
   at a time, through RESOURCE_PENDING bootstrap and then the existing sequence:
   PREPARED → LEGACY_QUIESCING → LEGACY_QUIESCED → IMPORT_READY → CAPABILITY_SEALED
   → STATE_IMPORTED → CANONICAL_AUTHORITY_ESTABLISHED → LEGACY_RETIRED → VERIFIED.
   Recheck complete inventory and fences on every step. No generation, upload,
   deployment, content dispatch or public success is inferred during this path.

7. At VERIFIED independently prove all three manual bridges and all retained/
   retired targets are disabled/drained, all six service boundaries persist,
   code/policy/key/state match and exactly one controller/five workers remain.
   Stop. Controller scheduling/production activation is a separate decision and
   separate authorized implementation; there is no activation command in this PR.

Closed blocker 5.2 stays CLOSED and unchanged: Overview `OPwpR3ReV0k` contradicts
its claimed exact source/kind; Short `TKAwQMzvP6U` has no exact producer lineage;
historical capability `5QW2YCqMG6Q` remains quarantined until trusted coordinated
5.1 sealing. No newer/timestamp-nearest artifact substitution is permitted.
