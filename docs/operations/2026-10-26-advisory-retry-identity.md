# Advisory review after a bounded video retry

Production advisory run 40315426591 rejected valid item video-20261026-131504-d4ece4f847-a2 before reading immutable evidence. The shell preflight accepted only initial item IDs; the producer appends -a2/-a3 on bounded fresh-generation retries. The later missing state.json artifact error was a consequence, not the root cause.

The preflight now admits only initial IDs and the permitted second/third retry suffixes. Unbounded or malformed IDs still fail. Failed validation no longer attempts to upload nonexistent state, and failed reviews preserve their evidence branch for an exact rerun. Successful reviews retain normal temporary-branch cleanup. No authority capability or permission expansion is introduced.

Evidence branch kesher-video-review-40314746817 was deleted by the old always-cleanup path. Its original immutable commit is c5ab9621c7f316895ed63ad7b06b9de7c07c441c. Recovery must recreate that exact branch at that commit, then rerun the advisory workflow with the original evidence root, article hash and item ID; never fabricate a new review state.

Validation: executed the real Bash preflight in controlled environments; -a2/-a3 failed before the fix and pass after it. Initial ID remains accepted; -a1/-a4/-a20 and traversal suffixes remain rejected. 27 focused review/governance tests pass.
