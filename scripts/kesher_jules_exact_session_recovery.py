"""Read/urgently nudge ONLY two already-created owner Jules sessions.

No Jules create/list/delete calls, no new GitHub PR, and no publication side
effects. Each session is pinned to the source identity of its original brief.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request

API_BASE = "https://jules.googleapis.com/v1alpha"
REPOSITORY_SOURCE = "sources/github/yanivsa/kesher-website"
ALLOWED = {
    "2026-11-07": (
        "12373986704369655205",
        "טיפול בהורים מבוגרים וזוגיות",
        "couple-caregiving-aging-parents-20261107",
    ),
    "2026-11-08": (
        "8024239748767566734",
        "מעבר לחדר נפרד",
        "separate-room-transition-20261019-v1",
    ),
}
ACTIVE = {"IN_PROGRESS", "PAUSED", "AWAITING_USER_FEEDBACK", "PLANNING", "QUEUED"}
KNOWN = ACTIVE | {"COMPLETED", "FAILED", "AWAITING_PLAN_APPROVAL"}
PR_RE = re.compile(r"https://github[.]com/yanivsa/kesher-website/pull/[0-9]+/?$")


def expected_title(slot: str) -> str:
    if slot not in ALLOWED:
        raise ValueError("Unsupported publication slot; no Jules call performed")
    keyword_hash = hashlib.sha256(ALLOWED[slot][1].encode("utf-8")).hexdigest()[:10]
    return f"Kesher article {slot} kw-{keyword_hash}"


def session_name(payload: dict) -> str:
    name = str(payload.get("name") or payload.get("id") or "")
    return name if name.startswith("sessions/") else f"sessions/{name}"


def inspect_identity(payload: dict, slot: str) -> tuple[str, list[str]]:
    if session_name(payload) != f"sessions/{ALLOWED[slot][0]}":
        raise ValueError("Unexpected Jules session ID; aborting without write")
    title = str(payload.get("title") or "").strip()
    # Jules v1alpha may return the legacy slot title, an owner-brief keyword
    # hash from the original prompt, or omit title in a reduced GET response.
    # The hardcoded 19-digit existing session ID above is the authority.
    # We still refuse any title for another slot or arbitrary task.
    if title and not re.fullmatch(
        rf"Kesher article {re.escape(slot)}(?: kw-[0-9a-f]{{10}})?",
        title,
    ):
        raise ValueError("Jules title/slot identity mismatch; aborting without write")
    # Corroborate keyword/idea against the original prompt when the API
    # exposes it. Do not require a field Jules may redact on GET.
    prompt = str(payload.get("prompt") or "")
    if prompt and (ALLOWED[slot][1] not in prompt and ALLOWED[slot][2] not in prompt):
        raise ValueError("Jules source prompt keyword/idea mismatch; aborting without write")
    source_context = payload.get("sourceContext") or {}
    source = str(source_context.get("source") or "")
    if source and source != REPOSITORY_SOURCE:
        raise ValueError("Unexpected Jules source repository; aborting without write")
    state = str(payload.get("state") or "UNKNOWN").upper()
    if state not in KNOWN:
        raise ValueError(f"Unexpected Jules session state {state!r}; aborting without write")
    output_urls: list[str] = []
    for result in payload.get("outputs") or []:
        if not isinstance(result, dict):
            continue
        url = str((result.get("pullRequest") or {}).get("url") or "")
        if url:
            if not PR_RE.fullmatch(url):
                raise ValueError("Jules PR points outside trusted repository")
            output_urls.append(url)
    return state, output_urls


def request_jules(api_key: str, method: str, path: str, body: dict | None = None) -> dict:
    if not path.startswith("/sessions/") or "/" in path.removeprefix("/sessions/").split(":")[0]:
        raise ValueError("Only exact Jules session resource paths allowed")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        API_BASE + path,
        data=data,
        method=method,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Jules {method} HTTP {exc.code} (no credentials logged)") from None
    except urllib.error.URLError:
        raise RuntimeError(f"Jules {method} network unavailable (no credentials logged)") from None
    if not raw:
        return {}
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("Malformed Jules JSON response (no credentials logged)") from None
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected Jules JSON response shape")
    return result


def nudge_prompt(slot: str) -> str:
    _, keyword, idea = ALLOWED[slot]
    context = (
        "For baby room transition: distinguish AAP safe-sleep recommendations from "
        "parenting advice, do not claim unsafe early solitary sleep is recommended. "
        if slot == "2026-11-08" else
        "For caregiving/aging parents: avoid unsupported statistics, absolutes, "
        "or fabricated studies. "
    )
    return (
        f"OWNER RESUME OF THIS EXACT EXISTING SESSION ONLY. Publication slot {slot}; "
        f"idea_id={idea}; required keyword={keyword}. Continue and correct your existing "
        "changes within this SAME session/source branch; Do NOT create a separate article "
        "or Jules session. Finish the already-started article, repair exact brief/content "
        "violations and generated-file integrity issues, cite verified authoritative "
        "sources and include at least three live relevant internal /blog/ links and a "
        "working service CTA. " + context +
        "Do not invent hero photography or edit other generated files. "
        "When quality requirements pass, SUBMIT your existing changes as exactly ONE "
        "owner-scoped GitHub PR targeting yanivsa/kesher-website main using the "
        "existing AUTO_CREATE_PR behavior, then finish the session. "
        "No merge/deploy/upload is authorized until independent CI and media gates pass."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", choices=tuple(ALLOWED), required=True)
    parser.add_argument("--mode", choices=("check", "nudge"), default="check")
    args = parser.parse_args()
    api_key = os.getenv("JULES_API_KEY", "")
    if not api_key:
        print("BLOCKED: Jules API secret absent", file=sys.stderr)
        return 2
    sid = ALLOWED[args.slot][0]
    payload = request_jules(api_key, "GET", f"/sessions/{sid}")
    state, pr_urls = inspect_identity(payload, args.slot)
    print(json.dumps({"slot": args.slot, "session": f"sessions/{sid}", "state": state,
                      "pr_urls": pr_urls}, ensure_ascii=False))
    if args.mode == "check":
        return 0
    if pr_urls:
        print("Existing PR output found; no nudge or new PR requested.")
        return 0
    if state not in ACTIVE:
        print(f"Refused nudge of non-active state={state}; exact original session preserved.")
        return 0
    # Only a message to the existing session is permitted. No create/cancel/delete API.
    request_jules(api_key, "POST", f"/sessions/{sid}:sendMessage",
                  {"prompt": nudge_prompt(args.slot)})
    print(f"NUDGE_SENT to existing sessions/{sid}; publication remains gated.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as exc:
        print(f"JULES_EXACT_SESSION_RECOVERY_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
