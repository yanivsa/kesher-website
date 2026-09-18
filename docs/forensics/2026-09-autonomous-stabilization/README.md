# KESHER autonomous stabilization forensics

Status: inventory in progress; no production-stability claim.

`incident-index.json` contains every discovered pipeline-related PR/Issue, including closed/unmerged and draft work. `scope-exclusions.json` makes exclusions reviewable. UNKNOWN and null fields explicitly require adjudication. Keyword, file-overlap, and author-claim evidence must not be promoted to proven root causes.

Reproduce using `python3 scripts/forensics/inventory_kesher_history.py --cache <private-cache> collect` then `... build`. A fresh directory produces a fresh snapshot; an existing cache resumes that snapshot. Raw API data remains outside Git. No generation, upload, repair session, workflow dispatch, or secret access occurs.
