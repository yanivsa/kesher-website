# Trusted image recovery, 2026-10-27

Production failure: the stabilized controller classified a trusted image worker commit as Jules normalization drift. Re-normalization removed the image and eventually exhausted the three image dispatches.

The controller now adopts a new image head only after the full exact-head article, bytes and pixels proof passes. Genuine normalization requirements (including stale base records or out-of-scope files) remain enforced.

For already-normalized-away images, recovery proves the immutable historical image head and requires the current editorial record to match exactly except image/imageAlt. The worker restores that same record and same bytes and rebinds proof to the new commit. Both evidence-only and artifact recovery dispatches carry recovery_only and expected_head_sha; a moved head or invalid recovery proof cannot fall through to fresh generation. No attempt counters are reset.

Boundary regressions exercise real proof and worker commit payloads; changed editorial and moved-head cases fail closed. Focused tests and independent review passed. Hosted exact-head gates and live recovery must pass before claiming resolution; this assisted cycle does not count toward three autonomous cycles.
