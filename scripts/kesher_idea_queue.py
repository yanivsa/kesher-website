#!/usr/bin/env python3
"""Durable owner-idea queue helpers for the canonical Kesher controller."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Mapping

MAX_QUEUE = 100
MAX_HISTORY = 50
MAX_TOPIC_BRIEF = 15500
MAX_KEYWORD = 200
IDEA_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


class IdeaQueueError(RuntimeError):
    pass


def _clean(value: Any) -> str:
    return "\n".join(line.rstrip() for line in str(value or "").strip().splitlines()).strip()


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _fingerprint(idea_id: str, topic_brief: str, keyword: str) -> str:
    raw = json.dumps(
        {"idea_id": idea_id, "topic_brief": topic_brief, "required_primary_keyword": keyword},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def ensure_fields(state: dict[str, Any]) -> None:
    if not isinstance(state.get("idea_queue"), list):
        state["idea_queue"] = []
    if not isinstance(state.get("idea_history"), list):
        state["idea_history"] = []
    if "active_idea" not in state:
        state["active_idea"] = None


def carry_forward(state: dict[str, Any], previous: Any) -> None:
    """Preserve durable owner ideas when the daily controller rolls to a new cycle."""
    ensure_fields(state)
    if not isinstance(previous, dict):
        return
    previous_queue = previous.get("idea_queue")
    previous_history = previous.get("idea_history")
    previous_active = previous.get("active_idea")
    if isinstance(previous_queue, list):
        state["idea_queue"] = copy.deepcopy(previous_queue)[-MAX_QUEUE:]
    if isinstance(previous_history, list):
        state["idea_history"] = copy.deepcopy(previous_history)[-MAX_HISTORY:]
    if isinstance(previous_active, dict) and str(previous_active.get("status") or "") != "complete":
        state["active_idea"] = copy.deepcopy(previous_active)


def _all_records(state: dict[str, Any]) -> list[dict[str, Any]]:
    ensure_fields(state)
    rows: list[dict[str, Any]] = []
    rows.extend(row for row in state["idea_queue"] if isinstance(row, dict))
    if isinstance(state.get("active_idea"), dict):
        rows.append(state["active_idea"])
    rows.extend(row for row in state["idea_history"] if isinstance(row, dict))
    return rows


def ingest_from_env(state: dict[str, Any], env: Mapping[str, str], *, now_iso: str) -> str | None:
    """Append one owner idea idempotently. Returns queued/duplicate/None."""
    idea_id = _clean(env.get("KESHER_IDEA_ID"))
    topic_brief = _clean(env.get("KESHER_IDEA_TOPIC_BRIEF"))
    keyword = _clean(env.get("KESHER_IDEA_REQUIRED_PRIMARY_KEYWORD"))
    run_now = _truthy(env.get("KESHER_IDEA_RUN_NOW"))
    if not idea_id and not topic_brief and not keyword:
        ensure_fields(state)
        return None
    if not idea_id or not IDEA_ID_RE.fullmatch(idea_id):
        raise IdeaQueueError("IDEA_ID_INVALID")
    if not topic_brief or len(topic_brief) > MAX_TOPIC_BRIEF:
        raise IdeaQueueError("IDEA_TOPIC_BRIEF_INVALID")
    if not keyword or len(keyword) > MAX_KEYWORD or "\n" in keyword:
        raise IdeaQueueError("IDEA_PRIMARY_KEYWORD_INVALID")

    fp = _fingerprint(idea_id, topic_brief, keyword)
    for idx, row in enumerate(state.get("idea_queue") or []):
        if not isinstance(row, dict):
            continue
        if str(row.get("idea_id") or "") != idea_id:
            continue
        if str(row.get("fingerprint") or "") == fp:
            if run_now and str(row.get("status") or "") == "queued":
                row["run_now"] = True
                if idx > 0:
                    state["idea_queue"].pop(idx)
                    state["idea_queue"].insert(0, row)
                return "run_now_queued"
            return "duplicate"
        raise IdeaQueueError("IDEA_ID_CONFLICT")

    for row in _all_records(state):
        if str(row.get("idea_id") or "") != idea_id:
            continue
        if str(row.get("fingerprint") or "") == fp:
            return "duplicate"
        raise IdeaQueueError("IDEA_ID_CONFLICT")

    queue_full = len(state["idea_queue"]) >= MAX_QUEUE
    idle_run_now = run_now and str(state.get("status") or "") == "complete" and not isinstance(state.get("active_idea"), dict)
    if queue_full and not idle_run_now:
        raise IdeaQueueError("IDEA_QUEUE_FULL")

    record = {
        "idea_id": idea_id,
        "fingerprint": fp,
        "topic_brief": topic_brief,
        "required_primary_keyword": keyword,
        "run_now": run_now,
        "status": "queued",
        "requested_at": now_iso,
    }
    if run_now:
        state["idea_queue"].insert(0, record)
        return "run_now_queued"
    state["idea_queue"].append(record)
    return "queued"


def claim_next(state: dict[str, Any], cycle: str, *, now_iso: str) -> dict[str, Any] | None:
    ensure_fields(state)
    if isinstance(state.get("active_idea"), dict):
        return state["active_idea"]
    if not state["idea_queue"]:
        return None
    row = copy.deepcopy(state["idea_queue"].pop(0))
    row.update({"status": "claimed", "publication_slot": cycle, "claimed_at": now_iso})
    state["active_idea"] = row
    return row


def article_dispatch_inputs(state: dict[str, Any], inputs: Mapping[str, Any] | None) -> dict[str, str]:
    payload = {str(k): str(v) for k, v in dict(inputs or {}).items() if v is not None}
    active = state.get("active_idea")
    if not isinstance(active, dict):
        return payload
    slot = str(payload.get("slot") or "").strip()
    claimed_slot = str(active.get("publication_slot") or "").strip()
    if not claimed_slot:
        raise IdeaQueueError("IDEA_SLOT_MISMATCH")
    # Legacy/base controller dispatch paths may omit slot after an idea has already
    # been durably claimed. The claimed publication_slot is authoritative in that
    # case. An explicitly conflicting slot still fails closed.
    if not slot:
        slot = claimed_slot
        payload["slot"] = claimed_slot
    elif slot != claimed_slot:
        raise IdeaQueueError("IDEA_SLOT_MISMATCH")
    brief = _clean(active.get("topic_brief"))
    keyword = _clean(active.get("required_primary_keyword"))
    idea_id = _clean(active.get("idea_id"))
    if not brief or not keyword or not idea_id:
        raise IdeaQueueError("ACTIVE_IDEA_INVALID")
    trusted_suffix = f"Idea Request ID: {idea_id}\nRequired Primary Keyword: {keyword}"
    payload["topic_brief"] = f"{brief}\n\n{trusted_suffix}"
    return payload


def finalize_if_complete(state: dict[str, Any], *, now_iso: str) -> bool:
    ensure_fields(state)
    active = state.get("active_idea")
    if state.get("status") != "complete" or not isinstance(active, dict):
        return False
    slug = str((state.get("article") or {}).get("slug") or "").strip()
    article_url = str((state.get("article") or {}).get("url") or "").strip()
    if not slug and article_url:
        slug = article_url.rstrip("/").split("/")[-1].strip()
    outputs = {
        "slug": slug,
        "article_url": article_url,
        "long_url": str((state.get("long_video") or {}).get("youtube_url") or "").strip(),
        "short_url": str((state.get("short") or {}).get("youtube_url") or "").strip(),
    }
    if not (outputs["article_url"] and outputs["long_url"] and outputs["short_url"]):
        return False
    done = copy.deepcopy(active)
    done.update({"status": "complete", "completed_at": now_iso, "outputs": outputs})
    state["idea_history"].append(done)
    state["idea_history"] = state["idea_history"][-MAX_HISTORY:]
    state["active_idea"] = None
    return True
