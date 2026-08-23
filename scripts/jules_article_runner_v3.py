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
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if __package__:
    from . import jules_article_runner_core as core
    from . import jules_article_diagnostics as diagnostics
else:
    import jules_article_runner_core as core
    import jules_article_diagnostics as diagnostics

_legacy_build_prompt = core.build_prompt
_legacy_poll = core.poll
TERMINAL_SETTLE_SECONDS = 15 * 60


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


def poll(api_key: str, session: str, timeout_seconds: int = core.SESSION_SECONDS) -> tuple[str, str, str]:
    """Do not expose a PR as stable until its Jules session is terminal.

    Jules can emit a PR output before its AUTO_CREATE_PR session has actually
    stopped mutating that branch. Returning success at the first PR URL lets the
    trusted image worker commit image metadata while Jules is still active, and
    a later Jules commit can erase that trusted metadata. Keep the exact session
    authoritative and fail retryably until it reaches COMPLETED.
    """
    outcome, pr_url, message = _legacy_poll(api_key, session, timeout_seconds)
    if outcome != "PR_CREATED":
        return outcome, pr_url, message

    sid = session.removeprefix("sessions/")
    deadline = time.monotonic() + TERMINAL_SETTLE_SECONDS
    while time.monotonic() < deadline:
        current = core.request_json(
            "GET",
            f"{core.API_BASE}/sessions/{sid}",
            core.jules_headers(api_key),
        )
        state = str((current or {}).get("state") or "UNKNOWN").upper()
        urls = core.pr_urls(current if isinstance(current, dict) else {})
        if state == "COMPLETED":
            if not urls:
                return "COMPLETED_WITHOUT_PR", "", "Jules completed after previously exposing a PR, but no PR output remained"
            print(f"JULES_ARTICLE_TERMINAL_PR session={session} pr={urls[0]}", flush=True)
            return "PR_CREATED", urls[0], ""
        if state in core.TERMINAL_FAILURES:
            return "JULES_TERMINAL_FAILURE", "", f"Jules ended with terminal state {state} after exposing a PR"
        time.sleep(15)

    print(
        f"JULES_ARTICLE_PR_NOT_TERMINAL session={session} session_preserved=yes",
        file=sys.stderr,
        flush=True,
    )
    return (
        "JULES_TIMEOUT_SESSION_ACTIVE",
        pr_url,
        "Jules exposed a PR but the session remained active; exact session preserved for safe resume before trusted image mutation",
    )


def main() -> int:
    core.build_prompt = build_prompt
    core.poll = poll
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
