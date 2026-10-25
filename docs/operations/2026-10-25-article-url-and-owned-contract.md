# Article PR URL and owned quality contract recovery

Production article run 40222812230 created PR #1209, then rejected its canonical URL as unexpected. CI run 40225173243 subsequently failed 17 cutover safety tests because the new article omitted slug. The writer also omitted controllerManaged, evidence and serviceUrl; the missing ownership marker skipped managed quality requirements. Issue #1210 tracks this repair.

Root causes:
- Two raw-string PR URL regexes double-escaped the dot and numeric group, rejecting a normal GitHub PR URL.
- Tests mocked _exact_pr_candidate and _wait_for_same_pr_repair, so they never exercised the failing URL boundary.
- Trusted normalization only corrected an explicit false ownership marker, leaving an omitted marker untouched.

Fixes:
- Correct both regexes while preserving exact host/repository/path checks.
- Validate every worker-owned new PR article as controllerManaged using a copy, so untrusted writer metadata cannot disable evidence/link/CTA requirements.
- Trusted extraction marks its owned article and fills a missing slug from the existing identity; original inputs and existing main articles remain untouched.

Regression evidence: canonical real parser and repair-wait paths failed before the regex fix; omitted-marker/slug extraction failed before normalization. After repair, 139 focused tests passed, including negative URL tests, quality, normalization worker, controller, authority and governance tests. Independent review found no blocking findings. Required CI and production same-PR content recovery remain separate gates.

Learning: mock only remote IO at trust boundaries; run the real URL parsing and quality decision. Required metadata belongs to trusted normalization, not only to model prompts. Missing ownership metadata must never disable publication quality checks.

Recovery uses the same article, PR #1209 and Jules session 4096243870966297410. No duplicate article is needed. The cycle that needed this repair is assisted and cannot count toward the three consecutive clean acceptance cycles.
