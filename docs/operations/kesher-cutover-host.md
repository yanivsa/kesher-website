# Install the existing Schema-6 gateway on a persistent trusted host

This completes the operator path from the [original cutover runbook](../forensics/2026-09-autonomous-stabilization/production-cutover-runbook-20261004.md).
It uses `live_cutover.build_runtime`, `prepare_migration` and the original
nine-phase `Coordinator`. It is not a second migration mechanism. The host
must be independently administered; a Cloudflare Pages deployment or a Worker
with a similar name is not evidence that this Python service is installed.

**No production cutover, automation-state migration or article/media dispatch
was executed while preparing this change.** Commands below are for a separately
authorized operator after PR review and merge.

## Required independently installed boundaries

Before installation can pass preflight, an administrator must implement native
ports for all six exact resource IDs: GitHub, Jules, NotebookLM, YouTube,
Cloudflare and the actual image provider/project. Their interface and protected
credential classes are specified in `exclusion.py`. Each port implements
`inspect(repo)` and `exclude(repo, observed_revision, policy)` with fresh native
readback, the existing complete credential-retirement and resource-enforced
denial contract, CAS, and
restart-safe uncertain-response reconciliation. No receipt file, empty Actions
run list, environment flag, OIDC authentication or YAML retirement is a fence.

`production_ports.PREREQUISITES` is the authoritative list of unresolved native
requirements. In particular, NotebookLM consumer sessions and outstanding
YouTube resumable-upload capabilities must be independently excluded/settled;
deleting a Jules session is not proof that its writer stopped. A provider that
cannot enforce this boundary remains `PrerequisitePort` and refuses. Never
replace it with a callback returning configured success.

Install an administrator-owned module, e.g. `trusted_kesher_ports`, in the host's
isolated Python environment. Its `build()` returns `cutover_host.NativePorts`:

| Field | Required implementation |
| --- | --- |
| `github` | Native API client holding the isolated gateway GitHub credential, outside Actions. |
| `boundary` | Real GitHub resource/grant enforcement and complete readback, including predecessor tokens. |
| `external_ports` | Native ports for precisely the other five resources. |
| `separation_observer()` | Fresh native resource/credential separation proofs for overlapping infrastructure. |
| `key()` | Read the actual protected `NOTEBOOKLM_STATE_KEY` from host custody; never log it. |
| `key_binding()` | Fresh `{name, available, updated_at}` metadata for that same key binding. |
| `review_check()` | Independently verify approved host/config/native-adapter/transitive dependency bytes and secret custody on every call. |
| `authority_observer()` | Fresh `GitHubAuthorityObserver` under the persistent exclusive fence, with the approved code/policy/evidence/key bindings. |

The last observer must verify remote executable trees, full registrations and
all active-run statuses, and assert persistent resource protection before and
after observing. The fence must remain enforced across admission and subsequent
canonical effects; a temporary read lock is insufficient. Use the existing
observer/fence contracts, including infrastructure separation proofs. The
gateway App may perform only the existing guarded state CAS and retirement
operations; canonical credentials remain subject to exact persisted command
gates at each native resource. Actions never receives the gateway's general
mutation credential. Review every transitive factory dependency separately;
pinning the factory module alone does not establish their trust.

## Install immutable reviewed code and durable storage

Use Linux with a persistent disk and independently managed TLS ingress.
Replace `REVIEWED_MAIN_SHA` with the exact **merged, independently reviewed**
main commit, not this PR's base SHA. Run host-administration commands as root:

```sh
useradd --system --home-dir /var/lib/kesher-cutover --shell /usr/sbin/nologin kesher-cutover
install -d -m 0755 /opt/kesher-cutover
install -d -m 0750 -o root -g kesher-cutover /etc/kesher-cutover
install -d -m 0700 -o kesher-cutover -g kesher-cutover /var/lib/kesher-cutover
git clone git@github.com:yanivsa/kesher-website.git /opt/kesher-cutover/code
git -C /opt/kesher-cutover/code checkout --detach REVIEWED_MAIN_SHA
python3.12 -m venv /opt/kesher-cutover/venv
/opt/kesher-cutover/venv/bin/python -m pip install -r /opt/kesher-cutover/code/scripts/requirements-cutover.txt
```

Install the reviewed native factory and its locked dependencies in that venv.
Keep code, venv, configuration and private evidence read-only to the service
user. Supply the gateway credential and sealing key through protected host
custody read by the native factory, never through repository/Actions variables
or request bodies. Review file ownership and writable parent directories;
the loader refuses relative paths, symlink files and group/world-writable JSON.

Initialize the invocation deny ledger **once** as the service user:

```sh
cd /opt/kesher-cutover/code
sudo -u kesher-cutover /opt/kesher-cutover/venv/bin/python -B - <<'PY'
from scripts.kesher_runtime.cutover_service import InvocationJournal
InvocationJournal.initialize('/var/lib/kesher-cutover/invocations.sqlite')
PY
```

Initialization uses exclusive creation and mode 0600. Replays are durably denied
before any step effect, including after restart. Missing/corrupt/insecure storage
fails closed. **Never delete/reinitialize a ledger to resolve a retry or restore
an unverified backup.** Reconcile durable remote intents and protected storage
before a fresh invocation. The ledger is not exclusion or migration evidence.

## Independently approve configuration and migration material

Install `/etc/kesher-cutover/installation.json` with root ownership and mode
0640 (group `kesher-cutover`). Its exact keys are:

```json
{
  "version": 1,
  "root": "/opt/kesher-cutover/code",
  "repo": "yanivsa/kesher-website",
  "repository_id": "EXACT_NATIVE_REPOSITORY_ID",
  "epoch": "INDEPENDENTLY_APPROVED_EPOCH",
  "owner": "INDEPENDENTLY_APPROVED_GATEWAY_PRINCIPAL",
  "gateway_url": "https://YOUR_INDEPENDENT_GATEWAY_ORIGIN",
  "ledger": "/var/lib/kesher-cutover/invocations.sqlite",
  "review": "/etc/kesher-cutover/review.json",
  "material": "/etc/kesher-cutover/migration-material.json",
  "closure": "/etc/kesher-cutover/closed-5.2.json",
  "bindings": "/etc/kesher-cutover/resources.json",
  "registrations": "/etc/kesher-cutover/registrations.json",
  "ports_factory": "trusted_kesher_ports:build"
}
```

All referenced JSON documents must be independently reviewed, protected regular
files at absolute paths. Duplicate JSON keys refuse. Do not use these placeholder
values as approved identities.

The review binds `repo`, `main_sha`, `code_sha256` (`executable_digest(root)`),
`policy_sha256` (`digest({'policy': rules, 'definitions': inventory(root,rules)})`),
`closed_evidence_sha256`, `closure_sha256`, `migration_material_sha256`,
`registrations_sha256`, `key_binding_sha256`, `legacy_commit_sha`,
`legacy_blob_sha`, `legacy_body_sha256` (canonical JSON digest), and
`ports_factory_sha256` (SHA-256 of the separately installed module's bytes).
These are measurements for independent approval, not a self-certification tool.

`resources.json` maps precisely the six resource names to actual native IDs.
`registrations.json` maps every current definition and retained historical/system
registration path to its exact observed integer ID. Unknown, missing, duplicate
or rebound IDs refuse. Inventory must be reconciled against the reviewed policy;
never reuse an old registration count. Required retired registrations must be
actually disabled and drained before preflight, including manual recovery paths.
Any remaining authority-topology policy change needs separate explicit review.

The existing closed-5.2 floor and exact archives stay in private custody and in
the approved migration material. Preserve the reviewed Overview contradiction,
Short's unproven producer lineage and historical capability quarantine; do not
substitute newer/nearest artifacts. The sealing key is required even if no
capability appears in a refreshed controller snapshot.

Migration material contains the existing `sources`, `artifacts`, `now`,
`historical_sources` where needed, and `retained_evidence` contracts. Include
`source_git_paths`, an exact source-key → catalog-path map for every material
source. Independently read **both** `src/data/posts.json` and
`src/data/postsRecent.json` at the pinned main SHA; missing, unreadable or duplicate
catalog identities refuse preflight. Preserve the actual fixed catalog path for
each source. A missing hero remains unverified and blocked; adoption does not
invent image or public-media evidence. The Oct6 and Oct10 recent publications
must be explicitly accounted for when those dates fall inside the reviewed
window. Re-review after main or the cutover date changes. Initial preflight
compares the reviewed cutover day to the trusted host clock's Israel date and
refuses a stale boundary. Later recovery retains the original immutable material;
this date check does not restart or invalidate an already fenced handover.

Material also contains a mandatory `post_freeze_boundary`:

```json
{
  "frozen_cycle": "2026-10-04",
  "cutover_slot": "2026-10-10",
  "adopted_source_keys": ["EXACT_SORTED_APPROVED_CANONICAL_SOURCE_KEYS"],
  "excluded_source_keys": ["EXACT_SORTED_REVIEWED_ALTERNATIVE_SOURCE_KEYS"]
}
```

For the approved revision/time, include **every exact current-main source from
the frozen cycle through the reviewed cutover day, inclusive**, with its full
independently fetched body. This includes an incomplete freeze-day article that
was published after the legacy snapshot. Keys use `SourceIdentity(...).key`;
never invent their string format. A reviewer explicitly assigns at most one
canonical source per occupied date to `adopted_source_keys`. Every other candidate
must appear in `excluded_source_keys`; the two disjoint, sorted lists must cover
the entire window. Excluded identities, same-day candidate sets, reviewed choice,
Git provenance and boundary digest are retained as quarantine evidence. A date
may be wholly excluded by explicit review; it acquires no canonical ownership.
No fixture choice in the regression tests is production approval.

Multiple adopted sources for a date, omitted alternatives, nonexistent identities,
expanded boundaries or conflicting active source bindings refuse. A source's
publication date defines eligibility, never ownership. If the review date/revision
changes, collect and review this boundary again. Older articles
are not automatically added as backlog. Existing current-day content is bound;
an empty current day stays eligible for normal article work and later independent
observation of its newly published main source. This exception applies only to
the reviewed empty cutover day; it cannot override any excluded identity.

In the Oct4→Oct9→Oct10 case, the exact Oct9 slug/date/content hash becomes a
canonical slot without fabricated receipts, worker ownership or completion.
Normal independent article/public-media observations verify existing Overview/Short
only with exact archived bytes and provider lineage already bound through the
existing migration/command contracts. URL/title/date metadata alone never adopts
ownership: an unbound public candidate blocks duplicate generation and requires
identity adjudication. Unknown inventory cannot generate media; independently
verified absence can make missing media eligible after article verification.
The observer uses a durable rotating backlog cursor, advances it on blocked
ambiguity, and skips completed backlog. Unreviewed duplicate-date slots retain
`SOURCE_AMBIGUOUS` and cannot authorize commands; they cannot starve Oct9 or
current-day work. Reviewed duplicate-date choices apply only when all observed
identities exactly match the approved candidate set. Unknown or missing identities
fail closed. The scheduler continues to alternate current/backlog work. Do not manufacture
Schema-6 JSON or directly overwrite automation-state.

Unbound prior-day slots are polled only when a persisted canonical article
command already intends work for that slot. This lets an Oct10 publication merged
on Oct11 become visible without adding arbitrary historical articles as backlog.

## Run the service and read-only production preflight

Install `deploy/kesher-cutover.service` and start it only under separate operator
authorization. It binds **127.0.0.1:8789**. Configure independent TLS ingress to
this listener with no other upstream mutation routes:

| Route | Contract |
| --- | --- |
| `GET /healthz` | Redacted installation/ledger health metadata; no readiness grant. |
| `GET /v1/authority` | OIDC-authenticated fresh native observation; only exact canonical main controller/worker identities after VERIFIED; no mutations or ledger claims. |
| `POST /v1/cutover/step` | The only remote mutation entrypoint: exact cutover workflow, protected `kesher-cutover` environment, current reviewed main, approved epoch/revision, one durable step per fresh invocation. |

No redirect, request state bundle, provider evidence, path, key, credential,
port/factory selection or caller-provided approval is accepted. Cutover identities
cannot be used as canonical authority-reader identities or vice versa.

```sh
install -m 0644 /opt/kesher-cutover/code/deploy/kesher-cutover.service /etc/systemd/system/kesher-cutover.service
systemctl daemon-reload
systemctl enable --now kesher-cutover.service
cd /opt/kesher-cutover/code
sudo -u kesher-cutover /opt/kesher-cutover/venv/bin/python -B -m scripts.kesher_runtime.cutover_host \
  --config /etc/kesher-cutover/installation.json preflight
```

The last command is **read-only** and exits nonzero on any missing prerequisite.
It verifies exact main/Schema-5 ref/blob/body, complete topology and run inventory,
one controller/five workers, actual retirement, authority pins, native ports and
actors, key binding/actual key availability, HTTPS gateway/ledger, approved
material/closed evidence, and exact post-freeze main-source completeness. It
performs pure migration preparation and final ref readbacks; it never acquires
fences, claims ledger entries, disables workflows, writes refs, dispatches,
creates migration state or calls generation/upload providers.

Run preflight immediately before the **first** cutover invocation, with main
and the reviewed legacy snapshot still unchanged. A green preflight is not
permission or live exclusion; native fencing is still required for the entire
handover. Later steps intentionally use the existing durable journal/original
blob and fresh native checks; do not try to reset state to satisfy initial
Schema-5 preflight during recovery.

After review, independently configure the protected environment and exact
repository `KESHER_CUTOVER_GATEWAY_URL` variable. Follow the original runbook's
one-new-invocation-per-step sequence and uncertain-response recovery. After
VERIFIED and independent resource/state/public proof, the **first controller
E2E is manual**: `gh workflow run kesher-content-controller.yml --repo
yanivsa/kesher-website --ref main`. This instruction is conditional, not executed
by this implementation. No schedule is enabled in this PR.
