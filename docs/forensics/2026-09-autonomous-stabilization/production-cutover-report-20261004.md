# Schema-6 production cutover implementation checkpoint

**VERDICT: BLOCKED. NO SCHEMA-6 PRODUCTION ACTIVATION HAS OCCURRED.**

The restartable Git/Actions cutover layer and authenticated service entrypoint
are implemented, tested and independently reviewed. Five external native ports
remain unavailable, and GitHub's complete predecessor-grant/direct-write-denial
boundary is an administrator prerequisite. The executable refuses these gaps;
no local evidence file can turn them into service authority. This Draft PR is
for code review and cannot be treated as permission to start production cutover.

The branch is `codex/schema6-production-cutover`. It began on exact requested
main `5fc62bce0df27a3ff02ab81d8ce156a23da355ab`, then preserved and independently
reviewed all six paths from three late commits through final main/merge base
`9947d0c67a86caa047d3c91d6bf33d9b1b68f0f2`. Validated implementation commit:
`1bd4c260e1fac3d9f1eb6541a0d92798d54304c3`. The containing evidence commit adds
only these reports/logs; find its exact SHA with:

```sh
git log -1 --format=%H -- docs/forensics/2026-09-autonomous-stabilization/production-cutover-report-20261004.md
git status --short
git diff --check origin/main...HEAD
```

The final delivery includes the exact containing SHA, worktree status and Draft
URL. Publication checks must re-read current main; a later move requires an
explicitly documented delta and renewed affected review before merge.

The sole new production cutover workflow is manual-only/main-only,
`.github/workflows/kesher-production-cutover.yml`, with explicit epoch/reviewed
revision and protected Actions OIDC. Its client sends one request to the
implemented credential-owning service; the service durably rejects attempt
replay before any effect. Exact registration reconciliation, Git epoch/main/state
CAS, durable Actions intent, all-five-status inventory, exact terminal-attempt
readback, resource fencing and all nine phases reuse the existing adapters and
Coordinator. It never generates, uploads, deploys, dispatches content, activates
the controller or infers public completion. The canonical controller stays inert.

GitHub's original 111 IDs remain preserved in the dated baseline. The fresh
inventory has 112 after late-main recovery dispatcher 374765037. Candidate has
74 policy definitions and 39 retained missing-YAML registrations; its new
cutover definition needs a separately reviewed service ID after merge, for 113
expected registrations. Retirement is exact-ID/path: 36 retired definitions,
three manual bridges, one bounded recovery dispatcher and 39 retained entries,
**79 total**. The two exact dynamic Dependabot registrations are handled through
durable intent, cancel and exact terminal readback. New/rebound registrations,
re-enable/rerun races and uncertain cancellations fail closed.

The five workers, controller and eight diagnostics stay outside the gateway's
retirement allowlist. All 19 infrastructure roles/service behavior are preserved;
CI adds the affected safety suites. Each infrastructure actor must demonstrate
real service separation against independently installed exact repo/policy/code
and all-six protected identities. CI's same-repository status grant, the YouTube
diagnostic's upload/metadata authority, and OCI/OpenClaw's incomplete effective
credential scopes cannot be replaced by configured attestations or silently
retired. The checkpoint lists every infrastructure path, ID, scope and missing
proof. No infrastructure workflow was disabled during this task.

The manual Video Overview, native Short and PR1054 deployment implementations
remain intact, with early state admission denying them once exclusion begins.
The late-main recovery dispatcher retains exact request push paths, main/current
day/exact-one-article checks and both unchanged worker operations. Its separate
admission mode cannot widen manual bridge permissions, and it must retire before
VERIFIED. Media mode, Hebrew `he`/`iw` verification, jealousy request/content,
native portrait/sharpness, plugin and legal bytes are preserved. Standard
generators' incidental whitespace/order changes were restored to main bytes.

Final validation passed with no failing gate waived: **1,198 Python**, including
**28 new cutover regressions**; **217 media policy**, **499 controller**,
**152 Vitest**, **140 browser** tests; **130 build routes** and **98 posts**.
Both actual root synthetic Overview/Short renders preserve decoded audio,
signature, duration and reusable provenance. Compilation, repository actionlint,
lint and diff checks pass. Lint has zero errors/17 configured-ignore warnings;
two duplicate-ZIP warnings exercise deliberate hostile archive fixtures. Prior
red failures and corrected intermediate runs remain in the hashed log archive.

Independent final source/policy review: **Critical 0 / Important 0**, with
**139 affected tests** independently passing. The two endpoint trust-root/target
findings, dynamic-path handling and callable transport ownership were repaired.
Batch recertification retains two complete fresh inventories and every exact
known terminal attempt without multiplying global reads per target. Reviewed
policy digest is
`ca0aafefd1d786f8cb05190d8937020dccd06c71bcc33a1740024a02ff7a2f3a`;
policy plus definitions digest is
`47f99a003bb6cdf5b086bcadfd2c9a87fff2250af8110b9a9a966da861c3a60b`.
All 1,481 callchain pins match; stale definitions, stale callchains and unknown
definitions are zero. Roles are 36 retired, 19 infrastructure, eight diagnostics,
three emergency bridges, five workers, one controller, one handover and one
retiring dispatcher. These are code checks, not native live retirement proof.

The read-only live state snapshot remained Schema 5, with no handover or GitHub
exclusion journal. `production_state_written=false`,
`production_activated=false`, `public_completion_inferred=false` for this task.
Concurrent work elsewhere is not represented as having been controlled here.

Closed blocker **5.2 stays CLOSED**. All five floor/adjudication/replay artifacts
are byte-identical to main. Overview `OPwpR3ReV0k` stays quarantined because its
exact archive contradicts claimed source/kind; Short `TKAwQMzvP6U` stays
quarantined because exact producer lineage is unproven; upload capability
`5QW2YCqMG6Q` stays quarantined until trusted coordinated 5.1 sealing. There was
no nearest-artifact replacement, sealing, import or production completion claim.

All six resource statuses are **HUMAN_PREREQUISITE**: GitHub algorithms/gateway
are automated but need a proven native complete grant boundary; Jules needs
predecessor key/repository authority and session retirement; consumer NotebookLM
needs cookie/master-token/session invalidation and native proof; YouTube needs
complete channel/OAuth/resumable-capability retirement and distinct canonical
OAuth project; Cloudflare needs complete account/member/key/token/integration
inventory/retirement; image providers need actual project/key/bearer/session
identity and settling. Every canonical credential must be distinguishable and
isolated from legacy definitions. If native proof remains unavailable, STOP
BLOCKED even after administrative credential changes.

The [runbook](production-cutover-runbook-20261004.md) supplies the exact conditional
post-merge sequence: independently review merged code/resource/registration/key
custody; install actual native enforcement and all 19 infrastructure boundaries;
install the independently reviewed service factory, protected durable denial
ledger/TLS/protected environment; bind the new cutover ID and exact merged main;
then manually invoke one epoch/revision-bound workflow per transition with fresh
readback. At VERIFIED prove all retired actors/bridges are drained and all six
boundaries persist, then STOP. Scheduling and activation remain separate work.

Evidence:
[checkpoint](production-cutover-checkpoint-20261004.json),
[validation](production-cutover-validation-20261004.json),
[672 input hashes](production-cutover-validation-inputs-20261004.json),
[independent review](production-cutover-independent-review-20261004.json),
[original registrations](production-cutover-registration-baseline-20261004.json),
[final registrations](production-cutover-registration-final-20261004.json),
[validation logs](production-cutover-validation-logs-20261004.tar.gz).

**Draft review only. Do not merge, activate, dispatch production work or schedule
the controller as part of this task.**
