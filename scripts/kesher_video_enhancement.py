#!/usr/bin/env python3
"""Shared V5/V6 Remotion enhancement contract for Overview and Short.

This module deliberately owns only the *optional* visual-enrichment layer. The
canonical NotebookLM product identity, audio, technical publication gate and
YouTube reconciliation remain owned by the existing pipelines/controller.

Contract:
- Overview and Short remain separate NotebookLM products.
- Missing optional assets never block publication.
- Unsafe/unverified/mismatched assets are dropped fail-closed.
- Rendering retries with optional assets removed, then with source-only visuals.
- A source-only/original fallback is allowed only when it still satisfies the
  caller's canonical technical gate.
"""

from __future__ import annotations

import copy
import hashlib
import shutil
from pathlib import Path
from typing import Any, Callable, Iterable

ENHANCEMENT_SCHEMA_VERSION = 1
SEMANTIC_FIT_MIN = 0.55

PROFILE_CONFIG: dict[str, dict[str, Any]] = {
    "overview_16_9": {"product": "overview", "width": 1280, "height": 720, "fps": 30},
    "short_9_16": {"product": "short", "width": 1080, "height": 1920, "fps": 30},
}

ALLOWED_ENHANCEMENT_STATUSES = {
    "enhancement_complete",
    "enhancement_partial",
    "enhancement_skipped",
    "asset_dropped",
    "fallback_source_only",
}

ALLOWED_TIMELINE_TYPES = {
    "broll",
    "image",
    "motion_graphic",
    "push_in",
    "pan",
    "reframe",
    "transition",
    "lower_third",
    "visual_hook",
    "source_video",
}

OPTIONAL_ASSET_TYPES = {"broll", "image", "motion_graphic"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_timeline(entries: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for raw in entries or []:
        entry = dict(raw)
        entry_type = str(entry.get("type") or "").strip()
        if entry_type not in ALLOWED_TIMELINE_TYPES:
            raise ValueError(f"unsupported edit-plan timeline type: {entry_type or '<empty>'}")
        start = float(entry.get("start") or 0.0)
        end = float(entry.get("end") or start)
        if end < start:
            raise ValueError("edit-plan timeline end precedes start")
        entry["start"] = round(start, 3)
        entry["end"] = round(end, 3)
        entry["type"] = entry_type
        entry.setdefault("fallback", "source_video")
        timeline.append(entry)
    return timeline


def _asset_drop_reason(asset: dict[str, Any]) -> str | None:
    asset_type = str(asset.get("type") or "").strip()
    if asset_type not in OPTIONAL_ASSET_TYPES:
        return "unsupported_asset_type"
    if str(asset.get("usage_status") or "").lower() != "approved":
        return "usage_not_approved"
    provenance = str(asset.get("provenance") or "").strip().lower()
    if not provenance or provenance in {"unknown", "unverified", "unclear"}:
        return "provenance_unverified"
    try:
        semantic_fit = float(asset.get("semantic_fit"))
    except (TypeError, ValueError):
        return "semantic_fit_missing"
    if semantic_fit < SEMANTIC_FIT_MIN:
        return "semantic_mismatch"
    if not str(asset.get("asset_ref") or "").strip():
        return "asset_ref_missing"
    if not str(asset.get("source") or "").strip():
        return "asset_source_missing"
    return None


def build_edit_plan(
    *,
    source_identity: str,
    profile: str,
    base_timeline: Iterable[dict[str, Any]] | None = None,
    asset_candidates: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a deterministic shared edit-plan contract for one exact product."""
    identity = str(source_identity or "").strip()
    if not identity:
        raise ValueError("source_identity is required")
    if profile not in PROFILE_CONFIG:
        raise ValueError(f"unknown enhancement profile: {profile}")

    timeline = _normalise_timeline(base_timeline)
    used: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []

    for raw in asset_candidates or []:
        asset = copy.deepcopy(dict(raw))
        reason = _asset_drop_reason(asset)
        if reason:
            dropped.append({**asset, "reason": reason})
            continue
        used.append(asset)
        start = float(asset.get("start") or 0.0)
        end = float(asset.get("end") or start)
        timeline.append(
            {
                "start": round(start, 3),
                "end": round(max(start, end), 3),
                "type": str(asset["type"]),
                "intent": str(asset.get("intent") or "visualize narration"),
                "asset_ref": str(asset["asset_ref"]),
                "fallback": "source_video",
                "provenance": str(asset["provenance"]),
                "source": str(asset["source"]),
                "usage_status": "approved",
                "semantic_fit": float(asset["semantic_fit"]),
                **({"sha256": str(asset["sha256"])} if asset.get("sha256") else {}),
            }
        )

    if used:
        status = "enhancement_complete"
    elif timeline:
        status = "enhancement_partial"
    elif dropped:
        status = "asset_dropped"
    else:
        status = "enhancement_skipped"

    config = PROFILE_CONFIG[profile]
    return {
        "enhancement_schema_version": ENHANCEMENT_SCHEMA_VERSION,
        "source_identity": identity,
        "profile": profile,
        "product": config["product"],
        "output": {"width": config["width"], "height": config["height"], "fps": config["fps"]},
        "render_mode": "full",
        "timeline": timeline,
        "assets_used": used,
        "assets_dropped": dropped,
        "enhancement_status": status,
    }


def publication_blockers(enhancement_status: str) -> list[str]:
    """Enhancement quality is never the canonical publication availability gate."""
    if enhancement_status in ALLOWED_ENHANCEMENT_STATUSES:
        return []
    return [f"blocking_enhancement_status:{enhancement_status}"]


def _reduced_plan(edit_plan: dict[str, Any]) -> dict[str, Any]:
    reduced = copy.deepcopy(edit_plan)
    reduced["render_mode"] = "reduced"
    reduced["timeline"] = [
        entry for entry in reduced.get("timeline", []) if entry.get("type") not in OPTIONAL_ASSET_TYPES
    ]
    if reduced.get("assets_used"):
        reduced["assets_dropped"] = list(reduced.get("assets_dropped") or []) + [
            {**asset, "reason": "optional_asset_removed_after_render_failure"}
            for asset in reduced.get("assets_used") or []
        ]
    reduced["assets_used"] = []
    reduced["enhancement_status"] = "asset_dropped" if reduced.get("assets_dropped") else "enhancement_partial"
    return reduced


def _source_only_plan(edit_plan: dict[str, Any]) -> dict[str, Any]:
    source_only = copy.deepcopy(edit_plan)
    source_only["render_mode"] = "source_only"
    source_only["timeline"] = [{"start": 0.0, "end": 0.0, "type": "source_video", "fallback": "source_video"}]
    source_only["assets_used"] = []
    source_only["enhancement_status"] = "fallback_source_only"
    return source_only


def execute_enhancement(
    *,
    source_path: Path,
    output_path: Path,
    edit_plan: dict[str, Any],
    renderer: Callable[[dict[str, Any], Path], None],
    source_publishable: bool,
) -> dict[str, Any]:
    """Run full → reduced → source-only, without triggering generation or upload.

    The supplied renderer is the existing Remotion renderer. If all three
    Remotion attempts fail, callers may copy the original source only when they
    have already established that the source itself meets the canonical output
    gate (for example an already-valid landscape Overview). Portrait Short
    callers normally pass ``source_publishable=False`` because Remotion owns the
    required 1080x1920 framing.
    """
    errors: list[str] = []
    candidates = [copy.deepcopy(edit_plan), _reduced_plan(edit_plan), _source_only_plan(edit_plan)]
    for candidate in candidates:
        mode = candidate["render_mode"]
        try:
            if output_path.exists():
                output_path.unlink()
            renderer(candidate, output_path)
            if not output_path.exists() or output_path.stat().st_size <= 0:
                raise RuntimeError("renderer returned without a non-empty output")
            status = candidate.get("enhancement_status") or "enhancement_partial"
            fallback_reason = "; ".join(errors) if mode != "full" and errors else None
            return {
                "enhancement_status": status,
                "render_mode": mode,
                "assets_used": candidate.get("assets_used") or [],
                "assets_dropped": candidate.get("assets_dropped") or [],
                "fallback_reason": fallback_reason,
                "attempt_errors": errors,
                "effective_plan": candidate,
            }
        except Exception as exc:  # renderer failures are deliberately bounded here
            errors.append(f"{mode}:{type(exc).__name__}:{exc}")

    if source_publishable and source_path.is_file() and source_path.stat().st_size > 0:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, output_path)
        return {
            "enhancement_status": "fallback_source_only",
            "render_mode": "original_source",
            "assets_used": [],
            "assets_dropped": _reduced_plan(edit_plan).get("assets_dropped") or [],
            "fallback_reason": "; ".join(errors),
            "attempt_errors": errors,
            "effective_plan": _source_only_plan(edit_plan),
        }

    raise RuntimeError("Remotion enhancement and source-only fallback both failed: " + "; ".join(errors))


def build_enhancement_manifest(
    *,
    source_path: Path,
    final_path: Path,
    edit_plan_path: Path,
    enhancement_status: str,
    assets_used: list[dict[str, Any]],
    assets_dropped: list[dict[str, Any]],
    fallback_reason: str | None,
) -> dict[str, Any]:
    if enhancement_status not in ALLOWED_ENHANCEMENT_STATUSES:
        raise ValueError(f"invalid enhancement status: {enhancement_status}")
    return {
        "enhancement_schema_version": ENHANCEMENT_SCHEMA_VERSION,
        "source_sha256": sha256_file(source_path),
        "final_sha256": sha256_file(final_path),
        "edit_plan_sha256": sha256_file(edit_plan_path),
        "enhancement_status": enhancement_status,
        "assets_used": copy.deepcopy(assets_used),
        "assets_dropped": copy.deepcopy(assets_dropped),
        "fallback_reason": fallback_reason,
    }
