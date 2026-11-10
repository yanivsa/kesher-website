# Temporary manual Schema-5 article canary

This bridge is available only for an owner-invoked workflow on `main` in
`yanivsa/kesher-website` while the independently read `automation-state` is
Schema 5, writable, and has neither `handover` nor `github_exclusion`.
Cutover retires/drains these emergency roles. No controller or schedule is
enabled. The canonical command-bound workers and gateway are unchanged.

## One article after this bridge PR is reviewed and merged

Choose the current Israel date and verify that neither publication catalog nor
an open article PR already owns it. The runner checks both `posts.json` and
`postsRecent.json`, exact-date PR collisions, and existing Jules sessions.
Uninspectable inputs or ambiguous sessions refuse. Do not use `test_mode=true`
for the production canary; that pre-existing explicit test mode bypasses date
guards and closes its test PR.

```sh
CANARY_SLOT="$(TZ=Asia/Jerusalem date +%F)"
gh workflow run kesher-article-generation.yml \
  --repo yanivsa/kesher-website --ref main \
  -f slot="$CANARY_SLOT" -f test_mode=false
```

An optional owner subject can be supplied with `-f topic_brief='...'`.
Wait for this exact generation run to succeed and its result artifact to name
the one article PR and terminal Jules session. A visible PR URL alone does not
prove Jules is quiescent. Failed/uncertain generation requires inspection of
the existing exact session/PR, not a replacement article or blind retry.

## Exact downstream path

1. Inspect the generated PR's exact head and changed files against current
   `main`. Jules writes text only; an absent hero is expected at this stage.
   Only the existing article-publication allowlist is acceptable. Existing
   articles must be unchanged and exactly one new article must match the slot.
   If the branch needs normalization, stop and repair that same PR under owner
   review. `normalize-article-pr.yml` remains retired; this bridge does not
   automatically normalize arbitrary branches or start content repair.
2. After the successful generation result and scope review, invoke the ONE
   additional restored component for that exact PR:

   ```sh
   gh workflow run kesher-article-image.yml \
     --repo yanivsa/kesher-website --ref main -f pr_number=ARTICLE_PR_NUMBER
   ```

   It independently rechecks Schema-5 bridge admission before any image
   credential/effect and uses the existing trusted-main V4 image worker. Its
   strict image evidence, provider/fallback checks and non-force head update
   remain. Fresh CI is dispatched for the image-bearing head. This does not
   dispatch article/media canonical commands or video/Short jobs.
3. Require successful current-head `verify` and all branch-protection checks.
   CI selects its maintained article profile only for pure publication paths;
   mixed changes require the full gate. Content, hero, build and distribution
   checks remain mandatory. Run the independent trusted article gate from a
   clean checkout of current `main`, never from candidate-controlled code:

   ```sh
   gh api repos/yanivsa/kesher-website/pulls/ARTICLE_PR_NUMBER > /tmp/article-pr.json
   gh api 'repos/yanivsa/kesher-website/pulls/ARTICLE_PR_NUMBER/files?per_page=100' \
     --paginate --slurp --jq 'add' > /tmp/article-files.json
   ARTICLE_HEAD="$(python3 -c 'import json; print(json.load(open("/tmp/article-pr.json"))["head"]["sha"])')"
   gh api "repos/yanivsa/kesher-website/commits/$ARTICLE_HEAD/check-runs?per_page=100" \
     --paginate --slurp --jq '{check_runs:[.[].check_runs[]]}' > /tmp/article-checks.json
   REPO=yanivsa/kesher-website GITHUB_TOKEN="$(gh auth token)" \
     python3 .github/scripts/validate-article-pr.py \
       /tmp/article-pr.json /tmp/article-files.json /tmp/article-checks.json
   ```

   Install the trusted checkout's existing `scripts/requirements-article.txt`
   first if its strict image decoder is unavailable. If head/main advances,
   reread and rerun the checks. Review evidence and public-source claims; a
   candidate's own reported success is not sole certification. Owner merges
   only the exact reviewed head using normal protection, never `--admin`.
   `auto-merge-article-prs.yml` remains retired.
4. After the reviewed article merge, invoke the already-existing guarded
   manual `deploy.yml` on `main`. It runs the full quality gate, renders a
   source-bound manifest, deploys and verifies publication. Independently
   confirm the exact article URL, source identity and hero in public HTML.

   ```sh
   gh workflow run deploy.yml --repo yanivsa/kesher-website --ref main
   ```

Video Overview and Short are later, separate owner-authorized steps using the
exact published source identity. This bridge does not dispatch or publish them.
No Schema-6 migration, gateway installation, automation-state write or cutover
is part of this procedure. A canary is not publicly complete until its exact
delivery is independently verified.
