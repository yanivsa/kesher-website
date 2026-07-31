#!/usr/bin/env python3
"""Enforce a terminal Jules automation result instead of trusting session creation."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = "https://jules.googleapis.com/v1alpha"
AUTONOMOUS_CLEANUP_GRACE_SECONDS = 600
WAITING_STATES = {"AWAITING_USER_FEEDBACK", "WAITING_FOR_USER"}
SUCCESS_STATES = {"COMPLETED"}
FAILURE_STATES = {"FAILED", "CANCELLED"}
CONTINUATION = (
    "Continue autonomously now. Do not ask the user another question and do not wait "
    "for confirmation, review, approval, or implementation choices. Refresh origin/main, "
    "choose the smallest safe repo-consistent path, and finish with either one focused "
    "validated non-draft PR or a factual clean no-op with no changeSet, branch, commit, "
    "push, or PR. Remove temporary artifacts and report the exact terminal evidence."
)
RECOVERY_SUFFIX = (
    "\n\nAUTONOMOUS RECOVERY REQUIREMENT: A previous session failed after emitting a "
    "progress/choice question. This replacement must not ask any question. Execute the "
    "smallest safe repo-consistent option through validation and a non-draft PR, or finish "
    "as a factual clean no-op with no changeSet, branch, commit, push, or PR."
)
INVALID_OUTPUT_CONTINUATION = (
    "Your COMPLETED state is invalid because it contains a changeSet without a pull "
    "request. Refresh origin/main, remove all inherited or incidental files, and finish "
    "the focused change as one validated non-draft PR. If the change is stale or cannot "
    "be isolated, remove the changeSet and finish as a true clean no-op. Do not ask a "
    "question and do not report COMPLETED again with a changeSet but no PR."
)


def request_json(
    method: str,
    path: str,
    api_key: str,
    body: dict | None = None,
    attempts: int = 3,
) -> dict:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            f"{API_BASE}{path}",
            data=data,
            method=method,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            retryable = error.code == 429 or error.code >= 500
            detail = error.read().decode("utf-8", errors="replace")[:1000]
            if not retryable or attempt == attempts:
                raise RuntimeError(
                    f"Jules API {method} {path} failed with HTTP {error.code}: {detail}"
                ) from error
        except urllib.error.URLError as error:
            if attempt == attempts:
                raise RuntimeError(
                    f"Jules API {method} {path} failed: {error.reason}"
                ) from error
        time.sleep(attempt * 5)
    raise RuntimeError(f"Jules API {method} {path} exhausted retries")


def session_name(response: dict) -> str:
    name = response.get("name") or response.get("session", {}).get("name")
    if not isinstance(name, str) or not name.startswith("sessions/"):
        raise RuntimeError(f"Creation response did not contain a session name: {response}")
    return name


def create_replacement(payload: dict, api_key: str) -> str:
    replacement = dict(payload)
    replacement["title"] = f"{payload.get('title', 'Jules automation')} (autonomous recovery)"
    replacement["prompt"] = f"{payload.get('prompt', '')}{RECOVERY_SUFFIX}"
    created = request_json("POST", "/sessions", api_key, replacement)
    name = session_name(created)
    print(f"Created one bounded autonomous replacement: {name}", flush=True)
    return name


def terminal_output_contract(session: dict) -> tuple[bool, str]:
    outputs = session.get("outputs") or []
    has_change_set = any("changeSet" in output for output in outputs)
    has_pull_request = any("pullRequest" in output for output in outputs)
    if has_change_set and not has_pull_request:
        return False, "COMPLETED with changeSet but no pullRequest"
    return True, f"{len(outputs)} output artifact(s)"


def watch(
    initial_session: str,
    payload: dict,
    api_key: str,
    max_seconds: int,
    poll_seconds: int,
    max_replacements: int,
) -> int:
    deadline = time.monotonic() + max_seconds
    current = initial_session
    continued: set[str] = set()
    replacements = 0
    last_state = ""
    invalid_completed_polls: dict[str, int] = {}

    while time.monotonic() < deadline:
        session = request_json("GET", f"/{current}", api_key)
        state = str(session.get("state", "UNKNOWN")).upper()
        if state != last_state:
            print(f"Jules terminal-state watchdog: {current} is {state}", flush=True)
            last_state = state

        if state in SUCCESS_STATES:
            valid, evidence = terminal_output_contract(session)
            if valid:
                print(
                    f"Jules session completed with {evidence}: {current}",
                    flush=True,
                )
                return 0

            polls = invalid_completed_polls.get(current, 0)
            if polls == 0:
                request_json(
                    "POST",
                    f"/{current}:sendMessage",
                    api_key,
                    {"prompt": INVALID_OUTPUT_CONTINUATION},
                )
                print(
                    f"Rejected false terminal success and requested cleanup: "
                    f"{current} ({evidence})",
                    flush=True,
                )
                # A false COMPLETED state often arrives near the workflow's original
                # deadline. Give the same session a bounded fresh window to submit or
                # clean up instead of timing out immediately after the correction.
                deadline = max(
                    deadline,
                    time.monotonic() + AUTONOMOUS_CLEANUP_GRACE_SECONDS,
                )
            invalid_completed_polls[current] = polls + 1
            if polls >= 5:
                if replacements >= max_replacements:
                    print(
                        f"Jules session retained invalid output after autonomous cleanup: "
                        f"{current} ({evidence})",
                        file=sys.stderr,
                    )
                    return 1
                current = create_replacement(payload, api_key)
                replacements += 1
                last_state = ""
            time.sleep(poll_seconds)
            continue

        if state in WAITING_STATES:
            if current not in continued:
                request_json(
                    "POST",
                    f"/{current}:sendMessage",
                    api_key,
                    {"prompt": CONTINUATION},
                )
                continued.add(current)
                print(
                    f"Continued waiting Jules session without user input: {current}",
                    flush=True,
                )
        elif state in FAILURE_STATES:
            if replacements >= max_replacements:
                print(
                    f"Jules session reached {state} after {replacements} replacement(s): "
                    f"{current}",
                    file=sys.stderr,
                )
                return 1
            current = create_replacement(payload, api_key)
            replacements += 1
            last_state = ""

        time.sleep(poll_seconds)

    print(
        f"Jules session did not reach a verified terminal state within {max_seconds}s: "
        f"{current}",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--response", required=True, type=Path)
    parser.add_argument("--max-seconds", type=int, default=2400)
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument("--max-replacements", type=int, default=1)
    args = parser.parse_args()

    api_key = os.environ.get("JULES_API_KEY", "")
    if not api_key:
        raise RuntimeError("JULES_API_KEY is required")

    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    response = json.loads(args.response.read_text(encoding="utf-8"))
    return watch(
        session_name(response),
        payload,
        api_key,
        args.max_seconds,
        args.poll_seconds,
        args.max_replacements,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"Jules terminal-state watchdog failed: {error}", file=sys.stderr)
        raise SystemExit(1)
