#!/usr/bin/env python3
"""Pipeline-v4 article runner: V3 identity guarantees plus pre-PR evidence review."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.parse
import sys
import time
from pathlib import Path

if __package__:
    from . import article_claim_quality as article_quality
    from . import jules_article_runner_v3 as v3
    from .kesher_primary_keyword_contract import parse_owner_required_keyword
else:
    import article_claim_quality as article_quality
    import jules_article_runner_v3 as v3
    from kesher_primary_keyword_contract import parse_owner_required_keyword

_v3_build_prompt = v3.build_prompt

SEARCH_FIRST_CONTRACT = r"""

--- CLICKABLE SEARCH-INTENT TITLE CONTRACT ---
This contract is mandatory (SEARCH-INTENT-FIRST) and must be completed BEFORE choosing the final topic,
title, slug, excerpt or article angle. It supersedes dry editorial naming and
keyword-first title preferences elsewhere in the article policy.

Goal: produce a Hebrew title that a real person would WANT to click because it
names a felt problem, promises a useful outcome, and creates honest curiosity —
while still matching language people actually search for.

1. Before drafting, perform live Hebrew search-language research using the search/
   web capabilities available in the Jules run. The Primary Search Query must be
   supported by at least one current OBSERVED QUERY SIGNAL: Google autocomplete/
   search suggestions, related searches, People Also Ask / equivalent user-query
   suggestions, or current first-party search-query data if it is genuinely
   available. Organic-result titles/snippets may help understand intent but are
   secondary evidence and are NOT sufficient by themselves to prove a query people
   use. Do not invent search volume, CPC, trend scores, autocomplete suggestions or
   Search Console data.
2. Select exactly ONE `Primary Search Query`: a natural Hebrew phrase/question a
   person could realistically type when looking for help with the chosen problem.
   Also record 2-3 close `Search Variants` that express the same intent.
3. BEFORE selecting the final title, generate at least FIVE materially different
   headline candidates internally. At least three must use a high-click editorial
   frame such as:
   - "איך [להשיג תוצאה רצויה] בלי [המחיר/הטעות/ההתנהגות הלא רצויה]"
   - "[בעיה יומיומית שמרגישים]? כך/מה עושים כדי [תוצאה מעשית]"
   - "למה [בעיה] קורה דווקא כש... ומה עושים במקום"
   - "[טעות/הרגל] שמחמיר את [הבעיה] — ומה אפשר לעשות אחרת"
   - "לפני שאתם [תגובה אינטואיטיבית]: נסו את הדבר הזה"
   - a concrete numbered promise ONLY when the article truly contains that exact
     number of steps/examples.
   Do not mechanically reuse one formula across consecutive articles.
4. Choose the strongest candidate by this order:
   A) instant relevance to a felt problem;
   B) clear practical payoff;
   C) honest curiosity / tension;
   D) natural spoken Hebrew;
   E) search-intent alignment.
   Search intent is a constraint, not permission to publish a boring title.
5. The final H1/article `title` must naturally contain the Primary Search Query or
   a close grammatical Hebrew variant, but it does NOT have to begin with the exact
   query. Put the human hook first when that materially improves click appeal.
   Abstract, academic, category-style or therapist-jargon titles are unacceptable
   when a concrete reader-facing formulation is possible.
6. Prefer language that sounds like the reader's inner monologue: "למה הוא...",
   "איך מפסיקים...", "מה עושים כש...", "רבים על...", "הילד לא...", "מרגישים ש...".
   Avoid labels such as "דינמיקה", "תהליכים", "ויסות", "פערי ציפיות", "סמכות
   הורית" or other professional abstractions in the visible title unless ordinary
   users genuinely use them and they improve clarity.
7. Use curiosity ethically. Never promise certainty, guaranteed outcomes, secret
   tricks, shocking discoveries, universal mistakes, or research claims the article
   cannot substantiate. A title may be punchy; it may not be misleading.
8. The `id`/slug, excerpt/opening answer and any SEO/meta title fields used by the
   repository must align with the SAME primary intent. The visible H1 may be more
   emotionally compelling than the SEO phrasing as long as both describe the same
   article accurately.
9. If no observed query signal can be found for a candidate topic, do NOT claim it
   is a searched term. Change the candidate/query and keep researching. Do not
   submit the article PR until at least one current observed query signal supports
   the Primary Search Query or a close variant.
10. In the PR body, include a compact audit block with these exact labels:
   `Primary Search Query: ...`
   `Search Variants: ...`
   `Search Evidence: ...`
   `Headline Frame: ...`
   The evidence line must name the observed query signal/source and must not claim
   numeric volume unless a real numeric source was available in the run.
11. Final click test: imagine the title alone in Google, WhatsApp or Facebook.
   If it reads like a lecture heading rather than something a stressed parent or
   couple would click now, rewrite it before submission.
--- END CLICKABLE SEARCH-INTENT TITLE CONTRACT ---
"""

VIRAL_TOPIC_DISCOVERY_CONTRACT = r"""

--- VIRAL TOPIC DISCOVERY CONTRACT ---
Run this stage ONLY when no repository-owner topic brief was supplied.

Goal: discover one timely, high-value Kesher article topic from recent public
conversation, then hand that single topic into the existing Hebrew search-intent
and evidence workflow. This is a topic-selection stage, not a trend-report stage.

1. Search recent public sources, prioritizing the last 7 days and expanding only
   when needed, across sources available to the Jules run such as YouTube, Reddit,
   X, public forums, practitioner discussions and reputable web sources.
2. Search in Hebrew and English. Use additional major languages when they produce
   useful leads that can be responsibly adapted for an Israeli audience.
3. Focus only on Kesher's editorial scope:
   - Couples: conflict cycles, stuck conversations, emotion-language instead of
     blame/silence, roommate-style relationships, intimacy, trust repair after
     crisis/infidelity, and premarital preparation.
   - Parenting: calm authority, boundaries with less friction/guilt, cooperation,
     family/sibling conflict, ADHD and emotional regulation, and gifted children
     including asynchronous development, perfectionism and sensitivity.
4. Internally generate 5-10 candidate topics, but select EXACTLY ONE final topic.
   Do not create a trend report, listicle of candidates, multiple articles, or
   multiple PRs.
5. Reject candidates that are already substantially covered in existing Kesher
   articles, are generic marketing advice, rely on unverifiable sensational claims,
   or fall outside Shira Saharoni's professional scope.
6. Prefer candidates that combine:
   - recent observable engagement/discussion;
   - one clear practical insight couples or parents can use;
   - a strong Israeli adaptation angle;
   - authoritative evidence available for material factual claims;
   - useful Hebrew search intent.
7. Treat viral content as DISCOVERY EVIDENCE, not automatic factual evidence.
   Preserve the original viral source URL/creator and observable engagement signals
   when available, but verify material claims separately with primary/authoritative
   sources. Never invent views, likes, shares, trend scores or engagement counts.
8. Deduplicate before drafting against current Kesher posts and open article PRs.
   If the leading candidate is already substantially covered, choose the next best
   candidate rather than creating a duplicate.
9. FALLBACK — if, after a bounded reasonable search, no candidate has enough
   observable engagement, Kesher relevance, verifiable support, or dedup safety to
   justify selection, DO NOT block the article run and DO NOT force a weak "viral"
   topic. Fall back to the pre-existing V3/base article topic-selection mechanism
   already present in the underlying prompt. That legacy mechanism remains the
   authoritative fallback. After it selects one topic, continue with the existing
   SEARCH-INTENT-FIRST TITLE CONTRACT and ARTICLE EVIDENCE CONTRACT.
10. Whether the topic came from viral discovery or the legacy fallback, create
    EXACTLY ONE article and one PR for the slot.
11. When viral discovery succeeds, include this compact audit block in the PR body:
    `Topic Discovery Source: ...`
    `Why Selected: ...`
    `Viral/Discussion Evidence: ...`
    `Primary Supporting Source: ...`
    `Duplicate Check: passed`
12. When the legacy fallback is used instead, do not fabricate viral evidence.
    Include:
    `Topic Discovery Source: fallback-to-legacy-selection`
    `Why Selected: no sufficiently strong current viral candidate`
    `Viral/Discussion Evidence: insufficient for selection`
    `Primary Supporting Source: ...`
    `Duplicate Check: passed`
--- END VIRAL TOPIC DISCOVERY CONTRACT ---
"""

CUSTOM_TOPIC_CONTRACT = r"""

--- OWNER-SUPPLIED TOPIC BRIEF CONTRACT ---
A repository-owner topic brief is present for this run. It is an authoritative
subject constraint, not merely a suggestion.

1. Keep the article on the supplied subject and professional perspective. Do not
   replace it with a different topic merely because another query appears more
   popular.
2. Search-intent research still controls the final Hebrew query/title wording
   inside this subject. If the exact supplied wording has no observed query signal,
   choose the closest natural supported query that preserves the same subject.
3. Treat claims from linked journalism, social posts or marketing material as leads
   to verify, not as automatically established facts. Prefer primary/authoritative
   sources for material statistics and safety claims, and attribute survey findings
   precisely.
4. Do not broaden a narrow finding into a general claim. In particular, distinguish
   shopping/product-recommendation trust from trust in parents generally unless
   evidence directly supports the broader statement.
5. Write original Kesher copy. Do not reproduce substantial source wording.
6. In the PR body include: Owner topic brief: applied.

7. When the owner topic brief specifies `Required Primary Keyword: <keyword>`, you MUST adopt that exact Primary Keyword in the title, opening paragraph, slug, and PR body audit block.

Owner topic brief:
{topic_brief}
--- END OWNER-SUPPLIED TOPIC BRIEF CONTRACT ---
"""


def load_owner_topic_brief() -> str:
    path = os.environ.get("KESHER_ARTICLE_TOPIC_BRIEF_FILE", "").strip()
    if path:
        try:
            brief = Path(path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise v3.core.ArticleRunnerError(
                "ARTICLE_TOPIC_BRIEF_ERROR",
                f"cannot read owner topic brief file: {exc}",
            ) from exc
    else:
        brief = os.environ.get("KESHER_ARTICLE_TOPIC_BRIEF", "").strip()
    if len(brief) > 16000:
        raise v3.core.ArticleRunnerError(
            "ARTICLE_TOPIC_BRIEF_ERROR",
            "owner topic brief exceeds 16000 characters",
        )
    return brief


PRIMARY_KEYWORD_CONTRACT = r"""

--- PRIMARY KEYWORD CONTRACT ---
Every Kesher article must enforce an explicit Primary Keyword across title, URL slug, opening paragraph, and PR audit metadata.

1. Definition:
   - The Primary Keyword must be an explicit, targeted search term (1-4 words).
   - In Hebrew, the canonical form or a natural prefix variant (using Hebrew prefixes: ב, כ, ל, מ, ש, ה, ו...) is required.
   - If an owner topic brief specifies `Required Primary Keyword: <keyword>`, you MUST use that exact keyword.
2. Title / H1:
   - The final article title (H1) MUST contain the Primary Keyword (or close Hebrew prefix variant).
3. First Paragraph:
   - The Primary Keyword MUST appear in the opening of the article body — within the first sentence or the first 20-25 words of the first paragraph.
4. Slug / URL:
   - The article `slug`/`id` MUST semantically represent the Primary Keyword in clean, lowercase kebab-case English (e.g. 'גמילה מטיטול' -> 'potty-training-toddlers').
   - The resulting article URL must be `/blog/<slug>`.
5. PR Body Audit Block:
   - In the PR body, include the audit line:
     `- Primary Keyword: <exact keyword>`
--- END PRIMARY KEYWORD CONTRACT ---
"""

EVIDENCE_CONTRACT = r"""

--- ARTICLE EVIDENCE CONTRACT ---
Before submitting or updating the article PR, perform one explicit final claim audit.
This requirement is mandatory even when every other content/style check passes.

1. Re-read title, excerpt and article body sentence by sentence.
2. Flag any sentence that presents psychology, child development, giftedness,
   ADHD, executive functions, relationships, education, health, prevalence,
   causation or human behavior as a general fact, defining trait, universal rule
   or predictable reaction.
3. For every flagged sentence, do exactly one of the following:
   - rewrite it as a clearly limited/context-dependent observation using natural
     qualifiers such as "לפעמים", "אצל חלק", "יכול/ה", "עשוי/ה", "ייתכן",
     "במקרים מסוימים" or equivalent wording; OR
   - remove it if the article does not need it.
4. Never invent a study, source, statistic, diagnosis or professional consensus.
   If a factual claim genuinely requires external evidence and no authoritative
   source is available inside the task context/repository, prefer qualification
   or removal rather than pretending certainty.
5. Specifically reject formulations equivalent to a defining universal trait,
   including "אחד המאפיינים הבולטים של X הוא...", unless the sentence itself
   contains an explicit limitation making clear that it applies only to some
   people/situations.
6. Re-run the repository content checks after the final wording change.
7. Do not submit the PR until this self-check passes. In the PR body, add a short
   line confirming: `Article evidence self-check: passed`.
--- END ARTICLE EVIDENCE CONTRACT ---
"""


def preflight(slot: str, token: str) -> str:
    posts = v3._load_local_posts()
    if v3.test_mode_enabled():
        print(f"KESHER_TEST_MODE_BYPASS slot={slot} duplicate_guard=bypassed", flush=True)
        return "READY"

    brief = load_owner_topic_brief()
    required = parse_owner_required_keyword(brief) if brief else None

    if required:
        if any(
            isinstance(post, dict) and str(post.get("primaryKeyword") or "").strip() == required
            for post in posts
        ):
            return "ARTICLE_ALREADY_PUBLISHED"
    else:
        if v3.core.article_exists_for_slot(posts, slot):
            return "ARTICLE_ALREADY_PUBLISHED"

    prs = v3.open_article_prs_for_slot(token, slot)
    if required:
        prs = [
            pr for pr in prs
            if required in str(pr.get("title") or "")
            or required in str(pr.get("body") or "")
        ]

    if len(prs) > 1:
        raise v3.core.ArticleRunnerError(
            "DUPLICATE_ARTICLE_PRS",
            f"duplicate open article PRs detected for slot {slot}: {len(prs)}",
        )
    if len(prs) == 1:
        return f"ARTICLE_ALREADY_IN_PROGRESS pr={prs[0].get('number')}"
    return "READY"


def configure_session_identity(slot: str) -> None:
    if v3.test_mode_enabled():
        v3.configure_test_session_identity(slot)
        return
    brief = load_owner_topic_brief()
    required = parse_owner_required_keyword(brief) if brief else None
    if required:
        def _owner_title(candidate_slot: str) -> str:
            return v3.core.owner_slot_session_title(candidate_slot, required)

        v3.core.slot_session_title = _owner_title
    else:
        v3.core.slot_session_title = v3._legacy_slot_session_title


def build_prompt(slot: str, policy: str) -> str:
    topic_brief = load_owner_topic_brief()
    prompt = _v3_build_prompt(slot, policy)
    required = parse_owner_required_keyword(topic_brief) if topic_brief else None
    if required:
        prompt = prompt.replace(
            f"If current `main` already contains an article with `date == {slot}`",
            f"If current `main` already contains an article with Primary Keyword == '{required}'",
        )
        prompt = prompt.replace(
            f"or a currently open `Publish Kesher article:` PR already contains an article with `date == {slot}`",
            f"or a currently open `Publish Kesher article:` PR already targets the Primary Keyword '{required}'",
        )
    if not topic_brief:
        prompt += VIRAL_TOPIC_DISCOVERY_CONTRACT
    prompt += SEARCH_FIRST_CONTRACT + PRIMARY_KEYWORD_CONTRACT + EVIDENCE_CONTRACT
    if topic_brief:
        prompt += CUSTOM_TOPIC_CONTRACT.format(topic_brief=topic_brief)
    return prompt


def _github_posts_at_ref(token: str, ref: str) -> list[dict]:
    encoded_ref = urllib.parse.quote(ref, safe="")
    payload = v3.core.request_json(
        "GET",
        f"https://api.github.com/repos/{v3.core.REPO}/contents/src/data/posts.json?ref={encoded_ref}",
        v3.core.github_headers(token),
    )
    if not isinstance(payload, dict) or str(payload.get("encoding") or "") != "base64":
        raise v3.core.ArticleRunnerError("ARTICLE_PRE_PR_QUALITY_SOURCE_INVALID", "posts.json content payload is not base64")
    try:
        rows = json.loads(base64.b64decode(str(payload.get("content") or "")).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise v3.core.ArticleRunnerError("ARTICLE_PRE_PR_QUALITY_SOURCE_INVALID", "cannot decode posts.json for PR quality validation") from exc
    if not isinstance(rows, list):
        raise v3.core.ArticleRunnerError("ARTICLE_PRE_PR_QUALITY_SOURCE_INVALID", "posts.json is not an array")
    return [row for row in rows if isinstance(row, dict)]


def _exact_pr_candidate(token: str, pr_url: str) -> tuple[dict, dict]:
    match = re.fullmatch(rf"https://github\.com/{re.escape(v3.core.REPO)}/pull/(\d+)", pr_url.strip())
    if not match:
        raise v3.core.ArticleRunnerError("ARTICLE_PRE_PR_IDENTITY_INVALID", f"unexpected PR URL: {pr_url}")
    number = int(match.group(1))
    pr = v3.core.request_json(
        "GET",
        f"https://api.github.com/repos/{v3.core.REPO}/pulls/{number}",
        v3.core.github_headers(token),
    )
    if not isinstance(pr, dict) or int(pr.get("number") or 0) != number or str(pr.get("state") or "") != "open":
        raise v3.core.ArticleRunnerError("ARTICLE_PRE_PR_IDENTITY_INVALID", f"PR #{number} is not the expected open PR")
    base_sha = str((pr.get("base") or {}).get("sha") or "").strip()
    head_sha = str((pr.get("head") or {}).get("sha") or "").strip()
    if not base_sha or not head_sha:
        raise v3.core.ArticleRunnerError("ARTICLE_PRE_PR_IDENTITY_INVALID", f"PR #{number} is missing base/head identity")
    base_posts = _github_posts_at_ref(token, base_sha)
    head_posts = _github_posts_at_ref(token, head_sha)
    base_ids = {str(row.get("id") or row.get("slug") or "").strip() for row in base_posts}
    new_posts = [
        row for row in head_posts
        if str(row.get("id") or row.get("slug") or "").strip()
        and str(row.get("id") or row.get("slug") or "").strip() not in base_ids
    ]
    if len(new_posts) != 1:
        raise v3.core.ArticleRunnerError(
            "ARTICLE_PRE_PR_IDENTITY_INVALID",
            f"expected exactly one new PR article, found {len(new_posts)}",
        )
    article = dict(new_posts[0])
    article["controllerManaged"] = True
    return pr, article


def _wait_for_same_pr_repair(
    token: str,
    api_key: str,
    session: str,
    pr_url: str,
    prior_head_sha: str,
    timeout_seconds: int = 15 * 60,
) -> bool:
    match = re.fullmatch(rf"https://github\.com/{re.escape(v3.core.REPO)}/pull/(\d+)", pr_url.strip())
    if not match:
        raise v3.core.ArticleRunnerError("ARTICLE_PRE_PR_IDENTITY_INVALID", f"unexpected PR URL: {pr_url}")
    number = int(match.group(1))
    sid = session.removeprefix("sessions/")
    deadline = time.monotonic() + timeout_seconds
    continued = False
    approved = False
    resumed = False
    while time.monotonic() < deadline:
        current = v3.core.request_json(
            "GET", f"{v3.core.API_BASE}/sessions/{sid}", v3.core.jules_headers(api_key)
        )
        state = str((current or {}).get("state") or "UNKNOWN").upper()
        pr = v3.core.request_json(
            "GET", f"https://api.github.com/repos/{v3.core.REPO}/pulls/{number}", v3.core.github_headers(token)
        )
        head_sha = str(((pr or {}).get("head") or {}).get("sha") or "").strip().lower()
        changed = bool(head_sha and head_sha != prior_head_sha.strip().lower())
        if changed and state == "COMPLETED":
            print(f"ARTICLE_PRE_PR_REPAIR_TERMINAL pr={number} head={head_sha}", flush=True)
            return True
        if state in v3.core.TERMINAL_FAILURES:
            return False
        if state in {"AWAITING_USER_FEEDBACK", "WAITING_FOR_USER"} and not continued:
            v3.core.send_message(api_key, sid, "Continue autonomously. Finish the exact same PR repair and do not ask a question.")
            continued = True
        elif state == "AWAITING_PLAN_APPROVAL" and not approved:
            v3.core.request_json(
                "POST", f"{v3.core.API_BASE}/sessions/{sid}:approvePlan", v3.core.jules_headers(api_key), {}, max_attempts=1
            )
            approved = True
        elif state == "PAUSED" and not resumed:
            v3.core.send_message(api_key, sid, "Resume autonomously and finish the exact same PR repair.")
            resumed = True
        time.sleep(15)
    return False


def _record_pre_pr_quality(*, status: str, violations: list[str], repaired: bool) -> None:
    path = v3.core.result_path()
    if not path.is_file():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["pre_pr_quality_status"] = status
    payload["pre_pr_quality_violations"] = list(violations)
    payload["pre_pr_quality_repaired"] = bool(repaired)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def enforce_post_pr_quality() -> bool:
    path = v3.core.result_path()
    if not path.is_file():
        raise v3.core.ArticleRunnerError("ARTICLE_PRE_PR_QUALITY_RESULT_MISSING", "article result is missing")
    result = json.loads(path.read_text(encoding="utf-8"))
    if str(result.get("outcome") or "") != "PR_CREATED":
        return True
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    api_key = os.environ.get("JULES_API_KEY", "").strip()
    session = str(result.get("session_id") or "").strip()
    pr_url = str(result.get("pr_url") or "").strip()
    if not token or not api_key or not session or not pr_url:
        raise v3.core.ArticleRunnerError("ARTICLE_PRE_PR_QUALITY_IDENTITY_MISSING", "quality validation is missing token/session/PR identity")

    pr, article = _exact_pr_candidate(token, pr_url)
    prior_head_sha = str((pr.get("head") or {}).get("sha") or "").strip()
    violations = article_quality.full_article_violations(article)
    if not violations:
        _record_pre_pr_quality(status="passed", violations=[], repaired=False)
        print("ARTICLE_PRE_PR_QUALITY_PASSED repaired=no", flush=True)
        return True

    sid = session.removeprefix("sessions/")
    number = int(pr.get("number") or 0)
    error_text = "\n".join(f"- {item}" for item in violations)
    prompt = f"""Your existing Kesher article PR #{number} failed the deterministic pre-publication quality contract.

Repair THE SAME PR and THE SAME BRANCH only. Do not create a new branch or PR. Do not modify images, workflows, tests, scripts or packages.

Exact violations:
{error_text}

Fix the new article so it satisfies every listed violation. For evidence, use only genuine authoritative/reputable sources and never invent a study, statistic or URL. Ensure at least three distinct relevant internal /blog/ links and keep the declared service CTA linked. Re-check unsupported absolute/causal claims. Push the corrected text/index changes to the existing PR branch and finish this same Jules session autonomously."""
    v3.core.send_message(api_key, sid, prompt)
    if not _wait_for_same_pr_repair(token, api_key, session, pr_url, prior_head_sha):
        v3.core.emit_result(
            str(result.get("slot") or ""),
            "ARTICLE_PRE_PR_QUALITY_REPAIR_FAILED",
            retryable=True,
            message="same-session quality repair did not reach a new terminal PR head within the bounded repair window",
            session_id=session,
            pr_url=pr_url,
        )
        return False

    _, repaired_article = _exact_pr_candidate(token, pr_url)
    remaining = article_quality.full_article_violations(repaired_article)
    if remaining:
        _record_pre_pr_quality(status="failed", violations=remaining, repaired=True)
        v3.core.emit_result(
            str(result.get("slot") or ""),
            "ARTICLE_PRE_PR_QUALITY_FAILED",
            retryable=True,
            message=" | ".join(remaining[:5]),
            session_id=session,
            pr_url=pr_url,
        )
        return False
    _record_pre_pr_quality(status="passed", violations=[], repaired=True)
    print("ARTICLE_PRE_PR_QUALITY_PASSED repaired=yes", flush=True)
    return True


def persist_owner_keyword_result_metadata() -> None:
    """Bind owner keyword requirements to the trusted workflow result artifact.

    The article PR can edit its own body/content, so those are never authoritative
    for owner intent. This metadata is written by the trusted main-branch runner and
    later consumed by the GitHub merge gate through the exact controller run artifact.
    """
    result = v3.core.result_path()
    if not result.is_file():
        return
    brief = load_owner_topic_brief()
    required = parse_owner_required_keyword(brief) or ""
    payload = json.loads(result.read_text(encoding="utf-8"))
    payload["owner_required_primary_keyword"] = required
    payload["owner_topic_brief_sha256"] = hashlib.sha256(brief.encode("utf-8")).hexdigest() if brief else ""
    tmp = result.with_suffix(result.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(result)


def main() -> int:
    v3.configure_test_session_identity = configure_session_identity
    v3.preflight = preflight
    v3.build_prompt = build_prompt
    code = v3.main()
    if code == 0:
        if not enforce_post_pr_quality():
            return 1
        persist_owner_keyword_result_metadata()
    return code


def attach_failure_diagnostic() -> None:
    """Persist Jules session diagnostics for V4 failures/timeouts.

    V4 calls V3 as an imported module, so V3's __main__ failure hook does not run.
    Without this hook, the structured result loses the activity/progress evidence
    needed by the Controller/Supervisor to distinguish a stalled session from a
    provider/API failure.
    """
    api_key = os.environ.get("JULES_API_KEY", "").strip()
    path = v3.core.result_path()
    if not api_key or not path.is_file():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    session = str((payload or {}).get("session_id") or "").strip()
    if not session:
        return
    diagnostic = v3.diagnostics.diagnose(api_key, session)
    v3.diagnostics.attach_to_result(path, diagnostic)


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except (v3.core.ArticleRunnerError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"JULES_ARTICLE_V4_BLOCKED {exc}", file=sys.stderr, flush=True)
        exit_code = 1

    if exit_code != 0:
        try:
            attach_failure_diagnostic()
        except Exception as exc:
            print(
                f"JULES_ARTICLE_V4_DIAGNOSTIC_FAILED {type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )

    raise SystemExit(exit_code)
