# KESHER: exhausted historical deployment starvation

Production evidence: controller run 40219838123 returned blocked: prior-cycle article deployment attempts exhausted, although deploy run 40219496122 passed and the current article + long + Short chain was complete. Issue #1206 tracks the repair; Jules task 12041389646884950787 was started through the jules issue label.

Root cause: backlog preflight selected one newest candidate and returned globally blocked when that row exhausted its deploy budget. Existing tests verified eventual public recovery and deploy bounds, but did not combine an exhausted row with another eligible row.

Repair contract:
- Check each candidate at most once per tick, newest first.
- Keep exact public title/canonical/content-hash checks.
- Preserve exhausted row errors and budgets; do not remove or mark its delivery complete.
- Continue to another eligible row within the same tick.
- If every candidate is exhausted, return a factual wait for a completed current cycle; preserve the existing blocked result for an incomplete waiting cycle.
- Recheck public reality next tick so a later external publication can recover an exhausted row.
- Keep current actionable-cycle priority.

Validation: three behavioral regressions observed failing before repair and passing after repair; 118 focused backlog/controller/rollover/liveness/authority tests passed. Independent review found and reproduced two additional regressions: switching to a stale fallback collection could bypass a primary deployment budget, and shallow state views lost root history assignments. Both were observed RED and fixed; collection precedence is now fixed for the tick and selector history is written back with its existing bound. Required CI and production replay remain separate completion gates.

Learning: test queue fairness with multiple mixed-state rows, not only single-row failure handling. A green workflow or green deploy does not prove public article identity. Direct HTTP probes from the owner cloud environment returned 403, which is inconclusive about production publication; do not infer an outage or weaken the public identity gate.

Acceptance remains 3 consecutive clean automatic article + long + Short deliveries with public links, no duplicates and no manual intervention during counted cycles. The first recovered chain was assisted; clean count remains 0/3. This fix alone does not certify the full content process.
