# Phase 2 QA — ChatGPT Review

> Date: 2026-09-18
> Reviewed branch: `seo/search-intelligence-20260918`
> Reviewed remote commit: `cd8cd1ad`
> Reviewer: ChatGPT
> Status: APPROVED_WITH_CORRECTIONS

## Scope reviewed

Reviewed the remote versions of:

- `COLLABORATION.md`
- `phase2-search-intelligence.md`
- `raw-google-signals.csv`
- `serp-results.csv`
- `serp-observations.csv`
- `keyword-master.csv`
- `seed-topics.csv`

Also cross-checked selected current claims against official Ashdod municipality and Israeli health-system sources.

## What Phase 2 established reliably

1. The research produced a substantial Google Autocomplete evidence set.
2. It preserved a useful distinction between the two exposed Search Console queries and newly researched terms in most places.
3. The broad query `פגישה ראשונה` has materially mixed intent. It should not be treated as a clean dating target without long-tail qualification.
4. `ייעוץ זוגי אונליין` appears as an actual Google Autocomplete suggestion under the core couples-counseling seed and is commercially relevant to a service the site already states is available online.
5. `משבר זוגיות אחרי לידה` and `ריבים בזוגיות אחרי לידה` were preserved as actual Autocomplete observations.
6. `תרגילים לשיפור תקשורת זוגית`, `כמה עולה ייעוץ זוגי`, and `הדרכת הורים למתבגרים` were preserved as actual Autocomplete observations.
7. The clinical caution around social anxiety is justified: authoritative Israeli health sources treat social anxiety as a mental-health condition with diagnosis/treatment implications. Any Kesher content should stay clearly within parenting guidance/general support and referral boundaries.

## Evidence-coverage correction

The Phase 2 summary says all 36 seeds were fully analyzed in SERP with 100% coverage. The persisted evidence does not support that wording.

### Persisted raw-signal coverage

`raw-google-signals.csv` contains 340 rows:

- AUTOCOMPLETE: 306
- RELATED_SEARCH: 24
- PAA: 10
- PASF: 0

Raw Google signals are persisted for 26 of 36 seeds.

Ten seeds have no row in the raw-signal file. This is not necessarily a research failure: some terminal/long-tail queries may legitimately yield no autocomplete/PAA/related signal. But the file should be interpreted as "no persisted Google surface signal for this seed", not full signal coverage.

### Persisted organic SERP-result coverage

`serp-results.csv` contains 45 result rows covering 17 of 36 seeds.

`serp-observations.csv` contains summaries for all 36 seeds, including competitor domains and SERP-feature descriptions for seeds that have no corresponding persisted result rows.

Therefore:

- the 36 observation summaries may be useful analyst notes;
- they are not all independently auditable from `serp-results.csv`;
- Phase 3 must assign lower confidence to conclusions that depend only on a summary row without persisted supporting result rows.

Do not describe Phase 2 as "full 10-result SERP analysis for all 36 seeds."

## PAA limitation

The original Phase 2 target requested deeper PAA collection for high-priority seeds.

Only 10 PAA observations were persisted across all seeds.

This is acceptable given the documented Google bot/CAPTCHA limitation, but it is a material limitation and must be carried into Phase 3.

Do not infer the absence of a user question merely because no PAA row was collected.

## Keyword-master provenance corrections

Four Phase 2 rows overstate their provenance.

### AUTO-0006 — `יועצת זוגית באשדוד`

The exact phrase does not appear in `raw-google-signals.csv`.

It is a sensible local variation of the research seed `יועצת זוגית אשדוד` and the associated SERP was reviewed, but it should not be labeled as a persisted Autocomplete observation.

Use as a local research/strategy seed, not a verified Autocomplete row.

### AUTO-0011 — `מריבות על כסף בזוגיות`

This was a predefined research seed. It has persisted SERP-result evidence, but it was not discovered from Autocomplete/PAA/Related Search in the raw file.

Treat it as a SERP-reviewed research seed, not a Google-suggestion discovery.

### AUTO-0012 — `זוגיות עם בן זוג עם הפרעת קשב`

Same issue: predefined research seed with persisted SERP-result evidence, not a raw Google-surface discovery.

### AUTO-0013 — `חרדה חברתית אצל מתבגרים הדרכת הורים`

The exact phrase is not present in the raw signal file, despite being labeled RELATED_SEARCH.

The parental-guidance angle is strategically sensible and supported by the site's scope, but the exact phrase must be treated as synthesized until a Google-observed source is persisted.

## Demand-language correction

Do not use phrases such as:

- "ביקוש גבוה"
- "אחד הנושאים המבוקשים ביותר"
- "דפוס החיפוש הדומיננטי ביותר"
- "מבוקש מאוד"

based only on Autocomplete presence, SERP presence, or a small number of surface observations.

Phase 2 has no connected keyword-volume dataset.

Use neutral wording such as:

- observed in Autocomplete
- observed in Related Searches
- supported by multiple search-surface observations
- appears as a commercially relevant query
- SERP shows a distinct intent

## Strategic-scope correction

Phase 2 contains several final-strategy recommendations such as:

- CREATE a dedicated online service page
- UPDATE_EXISTING for specific articles
- prioritize particular drafts

Those are useful hypotheses, but Phase 3 owns the final strategy decision.

Treat Phase 2 recommendations as candidate actions only.

## Local Ashdod claims — accepted vs unsupported

Current official sources support that:

- Ashdod municipality operates a couples/family treatment station.
- The municipal service is subsidized for Ashdod residents according to household circumstances.
- Ashdod has a municipal parenting-support framework.

However, the following proposed differentiation claims are NOT verified from Kesher's site/repository:

- "immediate appointment availability"
- "no waiting lists"
- "full discretion" as a comparative promise

Do not publish or use those claims unless separately verified.

Also do not assert that Kesher "cannot compete on price" without an actual current price comparison.

A safer Phase 3 framing is to compare verifiable service attributes only.

## Social-anxiety boundary

Authoritative Israeli health sources describe social anxiety as a mental-health disorder and discuss professional diagnosis/treatment.

Decision:

If Phase 3 retains this topic, the recommended Kesher scope should be limited to:

- what parents may notice;
- how parents can communicate/support;
- when to encourage professional assessment;
- what parenting guidance can and cannot provide.

Do not position Kesher content as diagnosis, CBT treatment, psychiatric treatment, or a substitute for licensed mental-health care.

## Phase 3 confidence rule

For each cluster/action, Phase 3 must explicitly distinguish evidence strength:

### HIGH evidence
Examples:
- exact GSC query;
- persisted Autocomplete/PAA/Related Search;
- multiple persisted SERP result rows;
- clear existing-site/service match.

### MEDIUM evidence
Examples:
- seed was intentionally researched and has limited persisted SERP evidence;
- strong existing-site alignment but no direct Google-surface discovery.

### LOW evidence
Examples:
- only analyst summary;
- synthesized variant not present in raw observations;
- conclusions relying on unpersisted SERP notes.

Phase 3 must not assign a high-confidence CREATE action solely from LOW/MEDIUM evidence.

## Phase 3 readiness

Phase 2 is usable for Phase 3 after the canonical provenance corrections.

Phase 3 may proceed, but must:

1. treat Phase 2 as evidence, not as final strategy;
2. penalize weak provenance;
3. prefer existing-page improvements when intent overlap is high;
4. limit Wave 1 to 5–8 actions;
5. avoid unsupported service promises;
6. keep the sitemap/indexation issue open;
7. preserve the clinical boundary for teen social anxiety.
