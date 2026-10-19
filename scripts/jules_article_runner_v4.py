#!/usr/bin/env python3
"""Pipeline-v4 article runner: V3 identity guarantees plus pre-PR evidence review."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

if __package__:
    from . import jules_article_runner_v3 as v3
    from .kesher_primary_keyword_contract import parse_owner_required_keyword
else:
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


SEO_GAP_TOPIC_DISCOVERY_CONTRACT = r"""

--- SEO GAP TOPIC DISCOVERY CONTRACT ---
Run this stage ONLY when no repository-owner topic brief was supplied and either
the deterministic autonomous discovery mix selected `seo-gap` for this slot OR
the preceding VIRAL TOPIC DISCOVERY CONTRACT explicitly fell back to this stage.

Goal: select one high-value Kesher topic because there is evidence of real search
demand and a meaningful reader problem, not merely because the topic is editorially
interesting.

1. Inspect current Kesher articles and the most recent 30 posts before proposing a
   new topic. Reject close-intent candidates that would compete with an existing
   canonical URL; this new-article worker must not create a second page for the same
   search intent.
2. Research the problem landscape in ENGLISH FIRST to identify established user
   problems, terminology and authoritative evidence, then research HEBREW search
   language to discover how Israeli users actually phrase the need.
3. Internally generate 5-10 candidate gaps and rank them qualitatively by all four:
   - observed search signal / demand evidence;
   - intensity and specificity of the real parent/couple pain;
   - fit with Shira Saharoni's parenting-guidance or couples-counseling services;
   - low cannibalization risk against existing Kesher pages.
4. Evidence hierarchy for demand: genuine first-party Keyword Planner or Search
   Console data when it is actually available to the run; then Google Trends;
   then Google autocomplete/search suggestions, related searches, People Also Ask
   or equivalent query suggestions; then consistent SERP/community signals as a
   proxy. Never invent volume, CPC, impressions, trend scores or query suggestions.
5. Select EXACTLY ONE natural Hebrew Primary Search Query and one article topic.
   A candidate with high theoretical volume but weak reader pain/business fit may
   lose to a narrower candidate with clear intent and a real problem.
6. Prefer problem-led queries such as what parents/couples type when something is
   stuck, frightening, repetitive or disruptive. Avoid generic category pages,
   vague awareness topics and thin keyword variants.
7. Verify material health, development, education or relationship claims with
   primary/authoritative sources. Search-demand evidence is not factual evidence.
8. If no candidate has adequate search evidence plus a distinct intent, use the
   durable approved topic pool in the underlying policy to generate fresh candidates,
   but still validate the final Hebrew query before drafting. Never choose randomly.
9. Create EXACTLY ONE article and one PR for the slot.
10. In the PR body include this compact audit block:
    `Topic Discovery Source: seo-gap`
    `Why Selected: ...`
    `Search Demand Evidence: ...`
    `Reader Pain: ...`
    `Cannibalization Check: passed`
--- END SEO GAP TOPIC DISCOVERY CONTRACT ---
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
   topic. Fall back to the SEO GAP TOPIC DISCOVERY CONTRACT included immediately
   after this contract. Apply its search-demand, reader-pain and cannibalization
   ranking rules, then continue with the existing SEARCH-INTENT-FIRST TITLE CONTRACT
   and ARTICLE EVIDENCE CONTRACT.
10. Whether the topic came from viral discovery or the SEO-gap fallback, create
    EXACTLY ONE article and one PR for the slot.
11. When viral discovery succeeds, include this compact audit block in the PR body:
    `Topic Discovery Source: ...`
    `Why Selected: ...`
    `Viral/Discussion Evidence: ...`
    `Primary Supporting Source: ...`
    `Duplicate Check: passed`
12. When the SEO-gap fallback is used instead, do not fabricate viral evidence.
    Include:
    `Topic Discovery Source: fallback-to-seo-gap`
    `Why Selected: no sufficiently strong current viral candidate`
    `Viral/Discussion Evidence: insufficient for selection`
    `Search Demand Evidence: ...`
    `Reader Pain: ...`
    `Cannibalization Check: passed`
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


def autonomous_discovery_mode(slot: str) -> str:
    """Return the deterministic ownerless discovery mode for a publication slot.

    Every ten consecutive calendar dates contain exactly seven SEO-gap slots and
    three trend slots. Owner-supplied topic briefs bypass this selector entirely.
    """
    residue = date.fromisoformat(slot).toordinal() % 10
    return "trend" if residue in {7, 8, 9} else "seo-gap"


def autonomous_discovery_contract(slot: str) -> str:
    mode = autonomous_discovery_mode(slot)
    audit = f"\n\n--- AUTONOMOUS DISCOVERY MIX ---\nDiscovery Mix: {mode}\n--- END AUTONOMOUS DISCOVERY MIX ---\n"
    if mode == "trend":
        return audit + VIRAL_TOPIC_DISCOVERY_CONTRACT + SEO_GAP_TOPIC_DISCOVERY_CONTRACT
    return audit + SEO_GAP_TOPIC_DISCOVERY_CONTRACT


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
        kw_hash = hashlib.sha256(required.encode("utf-8")).hexdigest()[:10]

        def _owner_title(candidate_slot: str) -> str:
            return f"Kesher article {candidate_slot} kw-{kw_hash}"

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
        prompt += autonomous_discovery_contract(slot)
    prompt += SEARCH_FIRST_CONTRACT + PRIMARY_KEYWORD_CONTRACT + EVIDENCE_CONTRACT
    if topic_brief:
        prompt += CUSTOM_TOPIC_CONTRACT.format(topic_brief=topic_brief)
    return prompt


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
