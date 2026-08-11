#!/usr/bin/env python3
"""Ask Jules to review one cloud video evidence bundle and record its gates."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API_BASE = "https://jules.googleapis.com/v1alpha"
REPO = "yanivsa/kesher-website"
SOURCE = "sources/github/yanivsa/kesher-website"
FINAL_MARKER = "KESHER_REVIEW_JSON"
WAITING_STATES = {"AWAITING_USER_FEEDBACK", "WAITING_FOR_USER", "PAUSED"}
TERMINAL_FAILURES = {"FAILED", "CANCELLED", "CANCELED"}


class ReviewError(RuntimeError):
    pass


def request_json(method: str, path: str, api_key: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        method=method,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ReviewError(f"Jules API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ReviewError(f"Jules API network error: {exc.reason}") from exc


def load_pending(state_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    state_path = state_dir / "state.json"
    if not state_path.exists():
        raise ReviewError("state.json does not exist")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    pending = [item for item in state.get("items", []) if item.get("status") == "pending_review"]
    if len(pending) != 1:
        raise ReviewError(f"Expected exactly one pending review item, found {len(pending)}")
    return state, pending[0]


def expected_hashes(state_dir: Path, item: dict[str, Any]) -> dict[str, Any]:
    hashes = {
        "manifest_sha256": item.get("manifest_sha256"),
        "final_sha256": item.get("final_sha256"),
        "transcript_sha256": item.get("transcript_sha256"),
        "source_file_sha256": item.get("source_file_sha256"),
        "visual_review_sha256": item.get("visual_review_sha256"),
        "frame_sha256": {},
    }
    for relative in item.get("frame_paths") or []:
        path = state_dir / relative
        if not path.exists():
            raise ReviewError(f"Review frame is missing: {relative}")
        import hashlib

        hashes["frame_sha256"][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        if hashes["frame_sha256"][relative] != (item.get("frame_sha256") or {}).get(relative):
            raise ReviewError(f"Stored frame hash mismatch: {relative}")
    if len(hashes["frame_sha256"]) != 4:
        raise ReviewError("Exactly four frame hashes are required")
    if any(not value for key, value in hashes.items() if key != "frame_sha256"):
        raise ReviewError("Evidence hashes are incomplete")
    return hashes


def build_prompt(
    evidence_root: str,
    item: dict[str, Any],
    hashes: dict[str, Any],
) -> str:
    return f"""Perform one strict READ-ONLY Kesher Video Overview review. Do not edit the repository, create a branch/commit/changeSet/PR, generate another video, contact NotebookLM, or contact YouTube.

The exact secret-free evidence is already checked out in `{evidence_root}` on this session's starting branch. Do not use `gh`, GitHub APIs, network downloads, or files outside that directory. If the directory or a required file is missing, reject or report the blocker and do not approve anything.

Expected item: `{item['id']}`.
Expected evidence hashes (must recompute locally with sha256sum and match exactly):
{json.dumps(hashes, ensure_ascii=False, indent=2)}

Open `{evidence_root}/state.json` and locate the exact item. Open and visually inspect EACH of its four `frame_paths` plus `visual_review_path` using the available image-viewing capability. Read the COMPLETE Hebrew transcript, COMPLETE Hebrew source file, manifest, source title/topic, YouTube title, description and every tag.

Apply four gates fail-closed:
1. Technical is already machine-verified. Independently confirm the manifest identifies a 16:9 H.264 video lasting 90-180 seconds. Recompute every checked-out file hash. The MP4 is deliberately excluded; confirm its expected final SHA-256 is identical in state.json, the manifest and the expected hashes above.
2. Visual: reject English except the Kesher URL, gibberish, slide/card/chart presentation, cropped text, black frame, repeated/static layout, unreadable branding, or any visible mismatch. Describe what is actually visible in all four frames.
   The visible website label must be exactly `kesher.saharoni.com`, without `https://`, a trailing slash, or other protocol text. Require meaningful visual progression across the four samples: clearly different compositions, motion states and scene ideas that support the narration. Reject generic decorative motion, repetitive abstract layouts, or visually dull output that does not help tell the source's story. Remotion does not need to replace every original pixel in principle, but every retained area must be contextually useful and free of forbidden slides, cards, charts, English branding and cropped text.
3. Semantic: compare all four frames and the complete narration transcript with the complete source. Reject any topic mismatch, especially parenting/child versus couples/relationship, unsupported claims, or missing central subject.
4. Metadata: compare title, description and every tag with source and transcript. Reject unsupported metadata, default/generic metadata, English, or missing `https://kesher.saharoni.com`. Separately confirm that `generation_prompt` explicitly requests a female Hebrew voice; this confirms the required request was sent to NotebookLM, but do not claim the resulting voice was independently verified from transcript-only evidence.

You may approve only after doing the actual file reads and image inspection. Notes must be factual Hebrew. Finish with `{FINAL_MARKER}` on its own line followed by exactly one JSON object and no Markdown fence:
{{
  "item_id": "{item['id']}",
  "manifest_sha256": "...",
  "final_sha256": "...",
  "transcript_sha256": "...",
  "source_file_sha256": "...",
  "visual_review_sha256": "...",
  "frame_sha256": {{"relative/frame-1.png": "...", "relative/frame-2.png": "...", "relative/frame-3.png": "...", "relative/frame-4.png": "..."}},
  "frame_observations": ["תיאור פריים ראשון", "תיאור פריים שני", "תיאור פריים שלישי", "תיאור פריים רביעי"],
  "visual_status": "approved or rejected",
  "semantic_status": "approved or rejected",
  "metadata_status": "approved or rejected",
  "visual_note": "הערה עובדתית בעברית",
  "semantic_note": "הערה עובדתית בעברית",
  "metadata_note": "הערה עובדתית בעברית"
}}
"""


def create_session(api_key: str, prompt: str, item_id: str, review_branch: str) -> str:
    payload = {
        "title": f"Kesher Video Evidence Review {item_id}",
        "prompt": prompt,
        "sourceContext": {
            "source": SOURCE,
            "githubRepoContext": {"startingBranch": review_branch},
        },
        "requirePlanApproval": False,
    }
    created = request_json("POST", "/sessions", api_key, payload)
    name = created.get("name")
    if not isinstance(name, str) or not name.startswith("sessions/"):
        raise ReviewError("Jules creation response contained no session name")
    print(f"JULES_REVIEW_STARTED session={name}", flush=True)
    return name


def list_activities(api_key: str, session: str) -> list[dict[str, Any]]:
    activities: list[dict[str, Any]] = []
    token = ""
    while True:
        query = "?pageSize=100"
        if token:
            query += "&pageToken=" + urllib.parse.quote(token)
        page = request_json("GET", f"/{session}/activities{query}", api_key)
        activities.extend(page.get("activities") or [])
        token = str(page.get("nextPageToken") or "")
        if not token:
            return activities


def wait_for_message(api_key: str, session: str, timeout_seconds: int) -> str:
    deadline = time.monotonic() + timeout_seconds
    continued = False
    while time.monotonic() < deadline:
        current = request_json("GET", f"/{session}", api_key)
        state = str(current.get("state", "UNKNOWN")).upper()
        if state == "COMPLETED":
            messages = []
            for activity in list_activities(api_key, session):
                message = (activity.get("agentMessaged") or {}).get("agentMessage")
                if isinstance(message, str):
                    messages.append(message)
            marked = [message for message in messages if FINAL_MARKER in message]
            for message in reversed(marked):
                try:
                    parse_decision(message)
                except ReviewError:
                    continue
                return message
            if not marked:
                raise ReviewError("Jules completed without structured review JSON")
            raise ReviewError("Jules completed without parseable structured review JSON")
        if state in TERMINAL_FAILURES:
            raise ReviewError(f"Jules review ended with {state}")
        if state in WAITING_STATES and not continued:
            request_json(
                "POST",
                f"/{session}:sendMessage",
                api_key,
                {"prompt": "Continue the read-only evidence review autonomously. Do not ask a question. If evidence access fails, reject or report the blocker; never approve without inspection."},
            )
            continued = True
        time.sleep(10)
    raise ReviewError("Jules review timed out")


def parse_decision(message: str) -> dict[str, Any]:
    tail = message.split(FINAL_MARKER, 1)[1].strip()
    if tail.startswith("```"):
        tail = re.sub(r"^```(?:json)?\s*", "", tail, count=1, flags=re.IGNORECASE)
    try:
        decision, _ = json.JSONDecoder().raw_decode(tail)
    except json.JSONDecodeError as exc:
        raise ReviewError("Jules review JSON is invalid") from exc
    if not isinstance(decision, dict):
        raise ReviewError("Jules review decision is not an object")
    return decision


def validate_decision(decision: dict[str, Any], item: dict[str, Any], hashes: dict[str, Any]) -> None:
    if decision.get("item_id") != item["id"]:
        raise ReviewError("Jules reviewed the wrong item")
    for field in ("manifest_sha256", "final_sha256", "transcript_sha256", "source_file_sha256", "visual_review_sha256", "frame_sha256"):
        if decision.get(field) != hashes[field]:
            raise ReviewError(f"Jules evidence mismatch: {field}")
    observations = decision.get("frame_observations")
    if not isinstance(observations, list) or len(observations) != 4:
        raise ReviewError("Jules must describe exactly four frames")
    for observation in observations:
        if not isinstance(observation, str) or len(re.findall(r"[\u0590-\u05ff]", observation)) < 8:
            raise ReviewError("Each Jules frame observation must be substantive Hebrew")
    for gate in ("visual", "semantic", "metadata"):
        if decision.get(f"{gate}_status") not in {"approved", "rejected"}:
            raise ReviewError(f"Jules returned invalid {gate} status")
        note = decision.get(f"{gate}_note")
        if not isinstance(note, str) or len(re.findall(r"[\u0590-\u05ff]", note)) < 12:
            raise ReviewError(f"Jules returned a weak or non-Hebrew {gate} note")


def record_decision(state_dir: Path, decision: dict[str, Any], session: str) -> None:
    command = [
        sys.executable,
        "-u",
        str(Path(__file__).with_name("kesher_daily_pipeline.py")),
        "--review-item", decision["item_id"],
        "--visual-status", decision["visual_status"],
        "--semantic-status", decision["semantic_status"],
        "--metadata-status", decision["metadata_status"],
        "--visual-note", decision["visual_note"],
        "--semantic-note", decision["semantic_note"],
        "--metadata-note", decision["metadata_note"],
        "--reviewer-session", session,
    ]
    env = os.environ.copy()
    env["KESHER_STATE_DIR"] = str(state_dir)
    result = subprocess.run(command, env=env, text=True, check=False)
    if result.returncode != 0:
        raise ReviewError("Official pipeline rejected the Jules review decision")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--review-branch", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    args = parser.parse_args()
    api_key = os.environ.get("JULES_API_KEY", "").strip()
    if not api_key:
        raise ReviewError("JULES_API_KEY is missing")
    _, item = load_pending(args.state_dir)
    hashes = expected_hashes(args.state_dir, item)
    prompt = build_prompt(args.evidence_root, item, hashes)
    session = create_session(api_key, prompt, item["id"], args.review_branch)
    message = wait_for_message(api_key, session, args.timeout_seconds)
    decision = parse_decision(message)
    validate_decision(decision, item, hashes)
    record_decision(args.state_dir, decision, session)
    print(f"JULES_REVIEW_RECORDED session={session} item={item['id']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ReviewError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"JULES_REVIEW_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)
