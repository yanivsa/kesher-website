# Media regression fixture and evidence projection adjudication

This records the disposition of the ten failures in the 787-test run after trusted article CI was connected. It is a local test/implementation result, not production verification or legacy-controller retirement.

## Authoritative contract

- The task requires complete independent native Short content and a signature inside the final source seconds with underlying audio preserved.
- PR [#760](https://github.com/yanivsa/kesher-website/pull/760), merge `5d4f0a22285c365556b696f890ab878cfcd5626a`, and [#761](https://github.com/yanivsa/kesher-website/pull/761), merge `64ffe3a8e213bd59676b74f859bf43e65f1ac510`, removed the obsolete Short duration truncation/gates. Exact histories are indexed in `guard-adjudications.json`.
- PR [#853](https://github.com/yanivsa/kesher-website/pull/853), merge `5e1454fe044cf0c19c3125a83224ad91ee9c6a83`, replaced the appended signature with an in-content overlay. The repository-owner policy commit `017b03e3401994f8afc3442916fb6cfd13a9f8c6` was reread for this migration. A full-screen background does not independently prove an appended outro or an in-content overlay; source-bound timing and bytes decide that question.
- The stabilization's strict signature/native-origin/audio guards bind complete raw/final/segment/asset digests, source/final durations, audio provenance, independent provider IDs and generation attempt. `tests/test_media_provenance_contract.py` already supplies a complete synthetic record and rejects changed/missing hashes, shifted audio, appended timing, shared Overview identity and invalid attempts. `tests/real_media_render.py` separately checks actual generated media; fixture dictionaries are not evidence of real public uploads.

## Rulings

`B` means the test's positive input encoded an obsolete or incomplete proof; its expected result and negative coverage are preserved. `A` means the implementation violated the correct assertion and was fixed. No failure was waived and no validator condition was relaxed.

| Failing test | Ruling | Correction and retained invariant |
| --- | --- | --- |
| `test_kesher_e2e_readiness.test_delivery_contract_requires_canonical_overview_remotion_edit` | B | Supply complete valid Short evidence so the test actually isolates Overview pipeline rejection. Keep both ready and raw-NotebookLM rejection assertions. |
| `test_kesher_e2e_readiness.test_production_overview_signature_must_overlay_final_source_seconds` | B | Supply the same complete Short proof; the appended Overview duration still fails. |
| `test_kesher_optional_video_enrichment.test_missing_broll_and_assets_never_block_complete_delivery` | B | Optional assets remain optional; their absence no longer accompanies an unrelated invalid signature hash and missing audio/origin proof. |
| `test_kesher_v6_intervention_isolation.test_v6_parity_report_exposes_exact_v5_delivery_contract_without_dispatch` | B | Supply complete Short provenance while retaining exact public identities, no-dispatch checks and the green-workflow/incomplete-product negative test. This does not authorize V6 production control. |
| `test_media_voice_policy_contract.test_short_runtime_passes_generation_attempt_to_voice_validator` | B | Supply duration and valid source/audio/signature evidence; still require the original item, including attempt 3, to reach the actual voice-validator call. Voice acceptance rules are unchanged. |
| `test_video_upload_guard.test_short_candidate_passes_with_verified_signature_video` | B | Replace boolean-only signature claims and non-hex hashes with complete synthetic proof. Missing signature/segment and Overview-derived Short cases still reject. |
| `test_v5_delivery_watchdog_contract.test_portrait_public_upload_with_signature_is_a_valid_short` | B | Positive public-item fixture now includes complete signature/audio/native-origin proof. Landscape, missing-signature, SVG-only and Overview-segment cases still reject. |
| `test_v5_delivery_watchdog_contract.test_delivery_contract_requires_article_overview_portrait_and_signature_short` | B | Keep the exact expected deliverables and completion requirements; supply valid complete positive evidence. |
| `test_v5_delivery_watchdog_contract.test_runtime_controller_adopts_only_verified_portrait_signature_short` | B | The valid source item must first pass the unchanged strict adoption guard. |
| `test_v5_delivery_watchdog_contract.test_adopt_existing_short_adopts_svg_signature_remotion_proof` | B + A | After valid fixture migration, the source item was accepted but the completion assertion still failed: the runtime projection discarded origin/audio/signature evidence. Preserve those fields with deep copies and clear obsolete flags from the previous item. Renamed to describe its actual behavior: reject SVG-only, then preserve complete source-bound proof. |

## Reproduction and correction

The first focused run after fixture migration passed 46 of 47 tests. The remaining failure reproduced actual proof loss after adoption. An additional regression failed before implementation: an adopted complete item lost its signature proof and could not pass the guard in the projected state. The implementation now copies only explicit proof fields, including negative origin flags, and does not copy upload capabilities or arbitrary item fields. Mutating the returned artifact cannot mutate stored nested proof; changing the stored audio digest still fails validation.

After correction, 62 focused contract/provenance tests pass. Full Python discovery passed all 790 tests in 153.467 seconds; this precedes the additional article-CI body-race regression, which passed in its separate 47-test focused gate. The full project gate also passed: generation, lint, content, 186 video-policy tests, 375 controller tests, 86 Node tests, production build, distribution verification and all 116 browser tests. The bounded independent review found no Critical, Important or Minor issue and separately verified deep-copy isolation and exclusion of upload capabilities. The strict validators in `kesher_e2e_delivery_guard.py`, `kesher_video_upload_guard.py` and `kesher_short_pipeline_v4.py` are unchanged by this fixture/projection migration.

The legacy projection remains only until the coordinated retirement step; this patch neither adds a controller nor grants new authority. Canonical completion still requires independent fresh public A+B+C verification. Legacy fixture success does not substitute for actual migration, the canonical observer, full CI or production reconciliation.
