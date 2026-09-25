#!/usr/bin/env python3
"""Pipeline-v4 article runner: V3 identity guarantees plus pre-PR evidence review."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if __package__:
    from . import jules_article_runner_v3 as v3
else:
    import jules_article_runner_v3 as v3

_v3_build_prompt = v3.build_prompt

SEARCH_FIRST_CONTRACT = r"""

--- SEARCH-INTENT-FIRST TITLE CONTRACT ---
This contract is mandatory and must be completed BEFORE choosing the final topic,
title, slug, excerpt or article angle. It supersedes any editorial-first title
preference elsewhere in the article policy.

Goal: choose article names from the language real Hebrew-speaking users actually
search for, not from abstract editorial labels or professional jargon.

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
3. The final H1/article `title` must naturally contain the Primary Search Query or
   a very close grammatical Hebrew variant. Prefer the actual search language at
   the beginning of the title when it remains readable and human. An abstract,
   literary or category-style title that hides the query is not acceptable.
4. The `id`/slug, excerpt/opening answer and any SEO/meta title fields used by the
   repository must all align with the SAME primary intent. Do not target a different
   keyword in each field.
5. Search intent comes before editorial cleverness, but natural Hebrew comes before
   exact-match stuffing. Never repeat keywords unnaturally, manufacture awkward
   Hebrew, or add irrelevant high-volume terms merely for SEO.
6. Prefer problem/question phrasing users use (for example "למה...", "איך...",
   "מה עושים כש...", or a direct service/problem phrase) over internal labels such
   as "דינמיקה", "תהליכים" or category names when the latter are not the actual
   query language.
7. If no observed query signal can be found for a candidate topic, do NOT claim it
   is a searched term. Change the candidate/query and keep researching. Do not
   submit the article PR until at least one current observed query signal supports
   the Primary Search Query or a close variant.
8. In the PR body, include a compact audit block with these exact labels:
   `Primary Search Query: ...`
   `Search Variants: ...`
   `Search Evidence: ...`
   The evidence line must name the observed query signal/source and must not claim
   numeric volume unless a real numeric source was available in the run.
9. Re-read the proposed title as a user query. If someone seeing only the title
   cannot immediately tell which real search question/problem the article answers,
   rewrite it before submission.
--- END SEARCH-INTENT-FIRST TITLE CONTRACT ---
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


def build_prompt(slot: str, policy: str) -> str:
    prompt = _v3_build_prompt(slot, policy) + SEARCH_FIRST_CONTRACT + EVIDENCE_CONTRACT
    topic_brief = load_owner_topic_brief()
    if topic_brief:
        prompt += CUSTOM_TOPIC_CONTRACT.format(topic_brief=topic_brief)
    return prompt


def main() -> int:
    # V3 remains the implementation owner for slot-scoped identity, test mode,
    # safe Jules session reuse and terminal PR settling. Only the prompt contract
    # changes here.
    v3.build_prompt = build_prompt
    return v3.main()


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
