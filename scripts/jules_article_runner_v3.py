#!/usr/bin/env python3
"""Pipeline-v3 article runner adapter.

Jules owns article text only. The required article image is attached afterwards
by the trusted GitHub Actions image stage, which is the only stage allowed to
receive image-provider credentials.
"""

from __future__ import annotations

import json
import os
import sys

if __package__:
    from . import jules_article_runner_core as core
    from . import jules_article_diagnostics as diagnostics
else:
    import jules_article_runner_core as core
    import jules_article_diagnostics as diagnostics

_legacy_build_prompt = core.build_prompt


def build_prompt(slot: str, policy: str) -> str:
    base = _legacy_build_prompt(slot, policy)
    return base + f"""

--- PIPELINE V3 IMAGE-STAGE OVERRIDE ---
This section supersedes every image-generation, image-provider, image-fallback,
image-evidence, or no-image instruction inside the durable article policy above.

For publication slot `{slot}`, Jules owns ARTICLE TEXT ONLY. Do not call DeepAI,
Gemini, Unsplash, Pexels or any other image provider. Do not download, generate,
inspect, add, copy, modify or delete image binaries. The new article MUST omit
`image` and `imageAlt` when Jules submits the PR, and the PR body MUST NOT invent
image provenance fields.

A trusted GitHub Actions stage running code from `main` will attach the required
verified image to THE SAME PR after Jules finishes. That trusted stage owns
provider credentials and the Gemini -> Unsplash -> Pexels -> local-curated
fallback chain. An article cannot be published until that stage succeeds.
--- END PIPELINE V3 IMAGE-STAGE OVERRIDE ---
"""


def main() -> int:
    core.build_prompt = build_prompt
    return core.main()


if __name__ == "__main__":
    exit_code = 1
    try:
        exit_code = main()
    except (core.ArticleRunnerError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"JULES_ARTICLE_BLOCKED {exc}", file=sys.stderr, flush=True)
        exit_code = 1

    if exit_code != 0:
        api_key = os.environ.get("JULES_API_KEY", "").strip()
        path = core.result_path()
        if api_key and path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                session = str((payload or {}).get("session_id") or "").strip()
                if session:
                    diagnostic = diagnostics.diagnose(api_key, session)
                    diagnostics.attach_to_result(path, diagnostic)
            except Exception as exc:
                print(f"JULES_ARTICLE_DIAGNOSTIC_FAILED {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

    raise SystemExit(exit_code)
