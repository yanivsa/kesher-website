#!/usr/bin/env python3
"""Pipeline-v4 article runner: V3 identity guarantees plus pre-PR evidence review."""

from __future__ import annotations

import json
import sys

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
    return _v3_build_prompt(slot, policy) + SEARCH_FIRST_CONTRACT + EVIDENCE_CONTRACT


def main() -> int:
    # V3 remains the implementation owner for slot-scoped identity, test mode,
    # safe Jules session reuse and terminal PR settling. Only the prompt contract
    # changes here.
    v3.build_prompt = build_prompt
    return v3.main()


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except (v3.core.ArticleRunnerError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"JULES_ARTICLE_V4_BLOCKED {exc}", file=sys.stderr, flush=True)
        exit_code = 1
    raise SystemExit(exit_code)
