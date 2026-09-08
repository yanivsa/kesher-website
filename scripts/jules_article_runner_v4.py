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
    return _v3_build_prompt(slot, policy) + EVIDENCE_CONTRACT


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
