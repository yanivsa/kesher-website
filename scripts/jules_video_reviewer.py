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

The exact secret-free evidence is already checked out in `{evidence_root}` on this session's starting branch. Do not use `gh`, GitHub APIs, network downloads, or files outside that directory. If the directory or a required file is missing, report the blocker and do not invent evidence.

Expected item: `{item['id']}`.
Expected evidence hashes (must recompute locally with sha256sum and match exactly):
{json.dumps(hashes, ensure_ascii=False, indent=2)}

Open `{evidence_root}/state.json` and locate the exact item. Open and visually inspect EACH of its four `frame_paths` plus `visual_review_path` using the available image-viewing capability. Read the COMPLETE Hebrew transcript, COMPLETE Hebrew source file, manifest, source title/topic, YouTube title, description and every tag.

IMPORTANT: Jules is an ADVISORY reviewer here, not a publication gate. Your approved/rejected statuses are quality signals for improvement only. They must not be treated as permission to block a technically valid YouTube upload.

Apply four advisory review dimensions:
1. Technical is already machine-verified. Independently confirm the manifest identifies a 16:9 H.264 video lasting 90-180 seconds. Recompute every checked-out file hash. The MP4 is deliberately excluded; confirm its expected final SHA-256 is identical in state.json, the manifest and the expected hashes above.

2. Visual creative review — concentrate especially on the CORNERS, EDGES, SAFE MARGINS and SUPPORTING OVERLAYS. Treat the central roughly 70% of the frame as the primary storytelling area. Remotion should ideally ENRICH the main story rather than visually take over the entire screen. Favor purposeful peripheral additions: tasteful corner accents, edge motion, contextual icons or recognizable objects, subtle depth, light highlights, restrained labels, framing elements and small story cues. Flag designs that unnecessarily cover, compete with, or replace the central storytelling area.

   Inspect all four frames and describe what is actually visible. The visible website label must be exactly `kesher.saharoni.com`, without `https://`, a trailing slash, or other protocol text. Report English except the Kesher URL, gibberish, cropped text, black frames, unreadable branding, or obvious visual mismatch.

   Judge ENERGY, CLARITY and INTEREST — not just technical cleanliness. Prefer clear, recognizable, story-related visual ideas over unexplained decorative motion. Good examples depend on the article and can include a phone, bill, table, doorway, two people, distance/connection metaphor, conversation cue, home object, money cue, parenting object, calendar, message bubble, key, chair, cup, toy, or another concrete symbol that actually supports the narration. Avoid relying on meaningless circles, blobs, lines, floating geometric shapes, repeated gradients, or abstract animations that a viewer cannot connect to the story.

   Motion should feel intentional, elegant and lively. Across the four samples there should be visual progression, different compositions or story beats, and some emotional build — but not chaos, visual noise or childish effects. The target is a polished, emotionally engaging relationship/parenting editorial video, not a generic motion-graphics screensaver.

   If the output is visually dull, too abstract, repetitive, or overly full-screen, the `visual_note` MUST include 2-4 concrete actionable improvements. Prioritize what should change in the corners/edges/overlays, identify which abstract element is weak, and name a more meaningful visual device that could replace it. Do not merely say "make it more engaging".

3. Semantic: compare all four frames and the complete narration transcript with the complete source. Report any topic mismatch, especially parenting/child versus couples/relationship, unsupported claims, or missing central subject. Small stylistic paraphrases, metaphors or natural spoken-language variations are not by themselves serious defects when the original meaning is preserved.

4. Metadata: compare title, description and every tag with source and transcript. Report unsupported metadata, default/generic metadata, English, or missing `https://kesher.saharoni.com`. Separately confirm that `generation_prompt` explicitly requests a female Hebrew voice; this confirms the required request was sent to NotebookLM, but do not claim the resulting voice was independently verified from transcript-only evidence.

You may complete the review only after doing the actual file reads and image inspection. Notes must be factual Hebrew. Finish with `{FINAL_MARKER}` on its own line followed by exactly one JSON object and no Markdown fence:
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
  "visual_note": "הערה עובדתית בעברית, ואם נדרש שיפור ויזואלי — 2-4 פעולות קונקרטיות",
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
