# Blocker 5.2 — final exact-evidence adjudication

**CLOSED for the bounded evidence and sealing-preparation slice.** All three examined claims remain **RETAINED_QUARANTINE**. No new import binding was proven. This does not close 5.1 or establish safe production cutover.

## Exact claims examined

The authoritative replay input remains the retained 2026-09-27T20:34:33.607193+00:00 snapshot: main `89b4c190626fd204ed7d61c4c5e0db8ed039ff04`, controller blob `b41bb425fc54f4f8893d161b62898560c454bbf3`, schema 5. Later production state was not substituted.

The Overview and Short both claim publication date **2026-09-27**, slug **siblings-fairness-vs-equality**, full content SHA-256 **1db6d9749e5d56f6b1e2b7ec88665e4c0823ed496b2dc2b8e3ff8c395c9b3fef**.

| Field | Overview claim | Short claim |
| --- | --- | --- |
| Item | `video-20260927-201145-1db6d9749e` | `video-20260927-060128-27fc420058` |
| Source ID | `12a22ab7-ee7a-40d8-b298-90ba85a70577` | `dba8e151-2167-4741-82a2-78be482e0933` |
| Provider/artifact ID | `e04b50da-8a66-4565-b0db-6aaf7dc3c537` | `70c3c424-4671-424a-b200-efa7631507ff` |
| Task ID | UNKNOWN | UNKNOWN |
| YouTube ID | `OPwpR3ReV0k` | `TKAwQMzvP6U` |
| Generation attempt | UNKNOWN; controller retry counters are preserved, not reinterpreted | UNKNOWN; controller retry counters are preserved, not reinterpreted |
| Referenced run / attempt | `36332344258` / `1` | UNKNOWN; both run fields are null |
| Referenced workflow | `.github/workflows/kesher-daily-video.yml` | UNKNOWN |
| Referenced run checkout | `b8b7441c306b8ee49db323a168c1c271e6d7f21e` | UNKNOWN |
| Referenced archive | `10936680658`, `kesher-video-state` | UNKNOWN |

The original generation producer, command identity and its code revision remain UNKNOWN where no exact generation receipt exists. An archive-publishing run is not automatically the original generation producer. Exact run/attempt/job metadata and the checkout SHA in the referenced job log agree for the known archive publisher.

The historical capability claim is publication date **2026-09-18**, slug **dating-apps-exhaustion**, SHA-256 **46c8d80a4f18f7ff52a1cc0c9739a8c9fddb19a57600272e845c8ee003bf5a03**, kind **short**, generation attempt **1**. Item: `video-20260918-145430-46c8d80a4f`; source: `209f95d0-e9dd-4999-986d-7ed891b00e42`; task/artifact: `5920bf7c-4961-431e-adf0-857e0ee42aff`; YouTube: `5QW2YCqMG6Q`. Its retained archive is `10704214914` (`kesher-short-v4-state`), published by run `35749006786` / attempt `1`, workflow `.github/workflows/kesher-short-v4.yml`, checkout `638eb9e02c91b42b4e9c9965d6e1907857ae02fd`. The original generation run is UNKNOWN.

## Adjudication

1. **Overview — RETAINED_QUARANTINE.** Exact archive `10936680658` has 66 items but neither the claimed item nor provider artifact. Its same-source item is a different rejected `article_short`: `video-20260927-182326-1db6d9749e`, source `d4e921e9-5508-4134-bcdf-8aaae6c7a786`, task/artifact `263e4194-c1f0-4a3f-9f65-cc6c8c735eec`. Its `OPwpR3ReV0k` record is instead `video-20260927-020414-27fc420058`, type `article_short`, for **gifted-children-perfectionism-tears**, date **2026-08-18**, hash **27fc420058c548aa10a586479e7c79d7d646e4a4b057b10d438ad8cc33175d70**. These are explicit source/kind/provider conflicts, not an adoptable Overview.
2. **Short — RETAINED_QUARANTINE.** No exact producer workflow/run/attempt/code/archive is retained for this item/source/artifact/video combination. The controller's adoption pointer is `video-20260927-020414-27fc420058`, whose exact archived identity is the different gifted source above. The claimed Short item is absent from that archive. No timestamp, short hash prefix or same-slug alternative supplies the missing lineage.
3. **Historical capability — RETAINED_QUARANTINE.** Exact source/kind/item/provider/video identifiers survive, but actual trusted-runtime sealing has not occurred. Current archive retrieval returns **404**; the retained local archive matches its original service digest. Raw/final/render files and complete modern audio/signature/render provenance are unavailable, so no public completion or permission to resume an upload follows from this record.

The Overview archive's complete **1,265,804,546 bytes** match service SHA-256 `36bb760544d1b8297b4ee857510732414687b288b5c2d6b7cd2649e8ad2f088a`; ZIP CRC validation passed. The retained capability archive matches `44d2a3d3d05eb9b6210256ad48b8dc7adec32afa98dbc6affdd1e55ea58f5ee1` and its CRC validation passed. Both older replay archive digests were rechecked. Checks of the ten existing `FILE_FIELDS` path/digest pairs found 16 matching available files across the three witness records; missing files/provenance remain explicit in JSON. No frame, audio or public-delivery certification is claimed. Whole-archive integrity does not resolve contradictory item identity.

## Safe replay and capability preparation

The unchanged `prepare_migration` implementation was invoked against the same retained inputs, without a sealer or newly eligible archive rows. The new dated report is [migration-legacy-evidence-replay-20260928.json](migration-legacy-evidence-replay-20260928.json); full safe claim/archive/file evidence is [legacy-media-adjudication-20260928.json](legacy-media-adjudication-20260928.json). Older reports remain preserved.

- **32 media baselines; 64 distinct observed YouTube IDs.**
- **14 duplicate-upload groups; 1 ambiguous-media group.**
- **2 unresolved controller-stage claims; 1 unsealed-capability claim.**
- Existing baseline receipts, historical dates, video-claim mappings, archive origins, source Git origins, stage claims and retry budgets are unchanged.
- **`production_state_written=false`; `public_completion_inferred=false`; `production_activated=false`.** No remote mutation, provider job, upload, metadata edit, workflow dispatch or deployment occurred.

Repository secret metadata confirms **NOTEBOOKLM_STATE_KEY**, updated `2026-08-10T13:35:14Z`. Its value was not accessed. The canonical worker's workflow-to-environment binding and sealing path were inspected. AES-GCM authenticates repository, exact media target and purpose; the import receipt binds the item and capability reference. Metadata presence does not prove key validity inside a future runtime.

Synthetic offline material round-tripped successfully. Wrong repository, purpose, key, kind, full source hash and publication date each failed authentication. No actual capability was sealed or used. **Actual existing-key sealing, fresh inputs after quiescence, and coordinated CAS import remain prerequisites under 5.1.**

## Validation and preservation

**118 focused tests passed in 4.928s**, exit 0:

```text
/usr/local/bin/python3 -m unittest tests.test_kesher_runtime_migration tests.test_kesher_output_artifacts tests.test_kesher_media_audit tests.test_kesher_media_observer tests.test_kesher_media_state tests.test_kesher_provider_recovery tests.test_kesher_canonical_state tests.test_kesher_autonomous_controller -v
```

The actual replay passes canonical state validation and preservation assertions. All three exact targets return `LEGACY_EVIDENCE_UNRESOLVED` even with a synthetic complete empty video inventory; the auditor is never called. This is an offline quarantine probe, not a live YouTube observation. Existing source/kind validators reject incompatible archive witnesses. No implementation or replay logic changed; full Python discovery and frontend/browser gates were not rerun.

Private evidence and logs remain under `/Users/ninja/.codex/tmp/kesher-forensics-20260917`, including `legacy-evidence-focused-20260928.log`, exact archives/run/job evidence, and `migration-legacy-evidence-prepared-20260928.private.json`. Raw capabilities and credentials are excluded from committed reports.

The pre-existing checkpoint edit was precisely one extra complete copy of the HEAD document inserted into itself. The exact bytes were backed up privately as `checkpoint-report-pre-slice-20260928.local.md`; duplicate removal preserves every unique original byte before the requested update. No unrelated work was discarded.

**Next recommended slice: 5.1 offline coordinated handover/topology boundary, including trusted capability import and interrupted/competing-writer refusal — Extra High.** This is a recommendation only. No 5.1 implementation or activation was started. Stop after the local evidence commit and clean-worktree verification.
