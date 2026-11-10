# Pre-image text repair deadlock

Production evidence: controller run 40305955895 blocked on PR #1213 after three auto-merge dispatches. Merge run 40243795281 rejected the image-incomplete PR at preflight. The content preflight had detected missing evidence/service metadata but routed repair through the merge bridge, which requires a completed trusted image. No content repair was reached.

The controller now calls the existing bounded same-PR Jules text-repair adapter directly for content failures. The existing initial-plus-two-repairs cap, exact-head markers, no-image-mutation instruction and all image/publication gates remain intact. This does not reset exhausted production budgets; the late-head-change recovery remains responsible for a legitimately repaired branch.

PR #1209 separately exposed an absent trusted semantic mapping for מעבר גן באמצע שנה. Added the corresponding kindergarten/preschool concepts while retaining fail-closed behavior for unknown topics and unrelated slugs.

Validation: observed regression failures before implementation; focused controller/keyword/normalization tests pass. Real adapter test intercepts only HTTP, verifying a Jules session message followed by an exact-head GitHub marker, with no workflow/image/merge request. Authority manifest changes recertify existing hashes only; permissions unchanged.

Acceptance remains 0/3 clean automatic article+long+Short cycles. Existing assisted recovery does not count.

Independent review caught two further edge cases, now covered by observed RED→GREEN tests: a still-invalid new head after repair exhaustion must block explicitly, and repair history after 100 comments must be paginated to prevent duplicate same-head requests. A refused repair is terminal rather than indefinite waiting.
