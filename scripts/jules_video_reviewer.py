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

try:
    from kesher_daily_pipeline import REVIEW_FRAME_COUNT
except ImportError:
    from scripts.kesher_daily_pipeline import REVIEW_FRAME_COUNT


API_BASE = "https://jules.googleapis.com/v1alpha"
REPO = "yanivsa/kesher-website"
SOURCE = "sources/github/yanivsa/kesher-website"
FINAL_MARKER = "KESHER_REVIEW_JSON"
WAITING_STATES = {"AWAITING_USER_FEEDBACK", "WAITING_FOR_USER", "PAUSED"}
TERMINAL_FAILURES = {"FAILED", "CANCELLED", "CANCELED"}
MAX_STRUCTURED_OUTPUT_REPAIRS = 2
STRUCTURED_OUTPUT_REPAIR_GRACE_SECONDS = 60
PROJECT_DIR = Path(__file__).resolve().parents[1]
REMOTION_POLICY_PATH = PROJECT_DIR / ".github" / "prompts" / "jules-remotion-video-upgrade.md"


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


def load_remotion_policy() -> str:
    try:
        policy = REMOTION_POLICY_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ReviewError(f"Durable Remotion policy is unreadable: {REMOTION_POLICY_PATH}") from exc
    if not policy:
        raise ReviewError("Durable Remotion policy is empty")
    return policy


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
    if len(hashes["frame_sha256"]) != REVIEW_FRAME_COUNT:
        raise ReviewError(f"Exactly {REVIEW_FRAME_COUNT} frame hashes are required")
    if any(not value for key, value in hashes.items() if key != "frame_sha256"):
        raise ReviewError("Evidence hashes are incomplete")
    return hashes


def review_json_example(item_id: str) -> dict[str, Any]:
    frame_hashes = {
        f"relative/frame-{index}.png": "..."
        for index in range(1, REVIEW_FRAME_COUNT + 1)
    }
    observations = [
        f"תיאור פריים {index} עם פירוט עובדתי מספק בעברית"
        for index in range(1, REVIEW_FRAME_COUNT + 1)
    ]
    return {
        "item_id": item_id,
        "manifest_sha256": "...",
        "final_sha256": "...",
        "transcript_sha256": "...",
        "source_file_sha256": "...",
        "visual_review_sha256": "...",
        "frame_sha256": frame_hashes,
        "frame_observations": observations,
        "visual_status": "approved or rejected",
        "semantic_status": "approved or rejected",
        "metadata_status": "approved or rejected",
        "visual_note": "הערה עובדתית בעברית, ואם נדרש שיפור ויזואלי — 2-4 פעולות קונקרטיות",
        "semantic_note": "הערה עובדתית בעברית",
        "metadata_note": "הערה עובדתית בעברית",
    }


def build_prompt(
    evidence_root: str,
    item: dict[str, Any],
    hashes: dict[str, Any],
) -> str:
    policy = load_remotion_policy()
    example_json = json.dumps(review_json_example(item["id"]), ensure_ascii=False, indent=2)
    return f"""Perform one strict READ-ONLY Kesher Video Overview review. Do not edit the repository, create a branch/commit/changeSet/PR, generate another video, contact NotebookLM, or contact YouTube.

The exact secret-free evidence is already checked out in `{evidence_root}` on this session's starting branch. Do not use `gh`, GitHub APIs, network downloads, or files outside that directory. If the directory or a required file is missing, report the blocker and do not invent evidence.

Expected item: `{item['id']}`.
Expected evidence hashes (must recompute locally with sha256sum and match exactly):
{json.dumps(hashes, ensure_ascii=False, indent=2)}

The following durable repository policy is authoritative for this review. Apply it as written; do not replace it with remembered or generic Remotion guidance.

--- BEGIN DURABLE REMOTION POLICY ---
{policy}
--- END DURABLE REMOTION POLICY ---

Open `{evidence_root}/state.json` and locate the exact item. Open and visually inspect EACH of its {REVIEW_FRAME_COUNT} `frame_paths` plus `visual_review_path` using the available image-viewing capability. Read the COMPLETE Hebrew transcript, COMPLETE Hebrew source file, manifest, source title/topic, YouTube title, description and every tag.

IMPORTANT: Jules is a MANDATORY reviewer and strict publication gate. A video must not be uploaded unless the visual, semantic, and metadata gates are explicitly approved.

Apply these mandatory review dimensions:
1. Technical is already machine-verified. Independently confirm the manifest identifies a 16:9 H.264 video lasting 90-180 seconds. Recompute every checked-out file hash. The MP4 is deliberately excluded; confirm its expected final SHA-256 is identical in state.json, the manifest and the expected hashes above.

2. Visual creative review: inspect all {REVIEW_FRAME_COUNT} sampled frames and evaluate compliance with the durable Source-Video-First Remotion policy above. Report concrete violations or weaknesses visible in the evidence. Do not invent problems that are not visible in the supplied evidence. You MUST reject slide/card-like compositions, text-heavy panels, timeline or diagram layouts, repeated identical frames, or generic illustrative visuals instead of a continuous natural visual story.

3. Semantic: compare all {REVIEW_FRAME_COUNT} frames and the complete narration transcript with the complete source file. Report topic mismatch, unsupported claims, or missing central subject. Small stylistic paraphrases, metaphors, or natural spoken-language variations are not by themselves serious defects when the original meaning is preserved.

4. Metadata: compare title, description and every tag with source and transcript. Report unsupported metadata, default/generic metadata, English, or missing `https://kesher.saharoni.com`. Separately confirm that `generation_prompt` explicitly requests a female Hebrew voice (`השתמש בקול של אישה ישראלית, חם, טבעי, ברור ומקצועי לכל אורך הקריינות.`); this confirms the required request was sent to NotebookLM, but do not claim the resulting voice was independently verified from transcript-only evidence.

You may complete the review only after doing the actual file reads and image inspection. Notes must be factual Hebrew. Finish with `{FINAL_MARKER}` on its own line followed by exactly one JSON object and no Markdown fence. The JSON must contain exactly {REVIEW_FRAME_COUNT} frame hashes and exactly {REVIEW_FRAME_COUNT} frame observations. Use this shape:
{example_json}
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
    structured_output_repairs = 0
    next_structured_output_repair_at = 0.0
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
            error = (
                "Jules completed without structured review JSON"
                if not marked
                else "Jules completed without parseable structured review JSON"
            )
            now = time.monotonic()
            if structured_output_repairs < MAX_STRUCTURED_OUTPUT_REPAIRS:
                if now < next_structured_output_repair_at:
                    time.sleep(10)
                    continue
                request_json(
                    "POST",
                    f"/{session}:sendMessage",
                    api_key,
                    {
                        "prompt": (
                            "Your evidence review did not end in the required machine-readable "
                            f"format. Reuse only the evidence you already inspected. Reply with "
                            f"{FINAL_MARKER} on its own line followed by exactly one valid JSON "
                            "object matching the requested schema, with no Markdown fence or "
                            "trailing prose. Do not edit files or invent evidence."
                        )
                    },
                )
                structured_output_repairs += 1
                next_structured_output_repair_at = now + STRUCTURED_OUTPUT_REPAIR_GRACE_SECONDS
                deadline = max(deadline, now + STRUCTURED_OUTPUT_REPAIR_GRACE_SECONDS + 60)
                print(
                    "JULES_REVIEW_FORMAT_REPAIR "
                    f"session={session} attempt={structured_output_repairs}",
                    flush=True,
                )
                time.sleep(10)
                continue
            raise ReviewError(error)
        if state in TERMINAL_FAILURES:
            raise ReviewError(f"Jules review ended with {state}")
        if state in WAITING_STATES and not continued:
            request_json(
                "POST",
                f"/{session}:sendMessage",
                api_key,
                {"prompt": "Continue the read-only evidence review autonomously. Do not ask a question. If evidence access fails, report the blocker; never invent inspection results."},
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
    if not isinstance(observations, list) or len(observations) != REVIEW_FRAME_COUNT:
        raise ReviewError(f"Jules must describe exactly {REVIEW_FRAME_COUNT} frames")
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


def handle_non_fatal_review_error(state_dir: Path, error_message: str) -> bool:
    try:
        state_path = state_dir / "state.json"
        if not state_path.exists():
            return False
        state = json.loads(state_path.read_text(encoding="utf-8"))
        items = state.get("items", [])
        pending = [item for item in items if item.get("status") == "pending_review"]
        if len(pending) != 1:
            return False
        item = pending[0]
        if not item.get("technical_verified") or not item.get("final_mp4"):
            return False
        final_mp4 = state_dir / item["final_mp4"]
        if not final_mp4.is_file() or final_mp4.stat().st_size == 0:
            return False

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        item["visual_review_status"] = "unavailable"
        item["semantic_review_status"] = "unavailable"
        item["metadata_review_status"] = "unavailable"
        note = f"סקירת ג׳ולס לא הושלמה: {error_message}"
        if not isinstance(item.get("review_notes"), dict):
            item["review_notes"] = {}
        item["review_notes"]["visual"] = note
        item["review_notes"]["semantic"] = note
        item["review_notes"]["metadata"] = note
        item["reviewer_error"] = str(error_message)
        item["reviewed_at"] = now
        item["updated_at"] = now

        state["updated_at"] = now
        temp_path = state_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp_path, state_path)
        print(f"JULES_REVIEW_UNAVAILABLE {error_message}", file=sys.stderr)
        return True
    except Exception as exc:
        print(f"Failed to record non-fatal review failure: {exc}", file=sys.stderr)
        return False


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--review-branch", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    args, _ = parser.parse_known_args()
    try:
        raise SystemExit(main())
    except Exception as exc:
        if args and hasattr(args, "state_dir") and handle_non_fatal_review_error(args.state_dir, str(exc)):
            raise SystemExit(0)
        print(f"JULES_REVIEW_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)
