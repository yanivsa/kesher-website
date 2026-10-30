#!/usr/bin/env python3
"""Reconcile Kesher Short/video state without duplicate generation.

Unresolved work is processed oldest-first. Multiple items form a durable FIFO
backlog instead of a fatal conflict. Jules review is advisory: a new YouTube
upload is permitted after machine technical verification of the exact
source/video identity. Provider polling resumes persisted IDs instead of
creating duplicate videos.

V4 adds a durable ``released_without_short`` tombstone. Four fresh generation
rounds are the maximum (initial + three technical retries). Once that budget is
exhausted, or the V4 controller explicitly releases the article, the slug is
persisted as released and is never selected for generation again.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

if __package__:
    from . import kesher_daily_pipeline as pipeline
    from . import kesher_e2e_delivery_guard as delivery_guard
    from .kesher_automation_policy import load_policy
    from .kesher_video_upload_guard import validate_candidate as validate_upload_candidate
else:
    import kesher_daily_pipeline as pipeline
    import kesher_e2e_delivery_guard as delivery_guard
    from kesher_automation_policy import load_policy
    from kesher_video_upload_guard import validate_candidate as validate_upload_candidate

UNRESOLVED_STATUSES = {
    "source_selected", "source_added", "generating", "downloaded",
    "pending_review", "approved", "rejected", "uploading",
}
PROVIDER_PROGRESS_STATUSES = {"source_selected", "source_added", "generating", "downloaded"}
RELEASED_STATUS = "released_without_short"
# Initial generation + three replacement generations = four fresh videos max.
MAX_TECHNICAL_RETRIES = 3


def workflow_output(name: str, value: str) -> None:
    """Expose a workflow decision without making pending provider work fail."""
    path = (os.environ.get("GITHUB_OUTPUT") or "").strip()
    if not path:
        return
    with open(path, "a", encoding="utf-8") as output:
        output.write(f"{name}={value}\n")


def source_slug(item: dict[str, Any]) -> str:
    source = item.get("source") or {}
    return str(source.get("slug") or source.get("id") or "").strip()


def source_date(item: dict[str, Any]) -> str:
    source = item.get("source") or {}
    return str(
        source.get("date")
        or item.get("israel_date")
        or item.get("created_at")
        or item.get("updated_at")
        or "9999-12-31"
    )


def posts() -> list[dict[str, Any]]:
    return [row for row in pipeline.load_posts() if isinstance(row, dict)]


def authoritative_article() -> dict[str, Any]:
    today = pipeline.israel_now().date().isoformat()
    matches = [
        pipeline.source_metadata(post)
        for post in posts()
        if str(post.get("date") or "") == today
    ]
    if len(matches) != 1:
        raise pipeline.PipelineError(
            f"Expected exactly one authoritative article for {today}, found {len(matches)}"
        )
    return matches[0]


def current_source_snapshot(slug: str) -> dict[str, Any]:
    matches = [
        pipeline.source_metadata(post)
        for post in posts()
        if str(post.get("slug") or post.get("id") or "").strip() == slug
    ]
    if len(matches) != 1:
        raise pipeline.PipelineError(
            f"Expected exactly one published source for unresolved video {slug}, found {len(matches)}"
        )
    return matches[0]


def published_slugs() -> set[str]:
    return {
        str(post.get("slug") or post.get("id") or "").strip()
        for post in posts()
    }


def unresolved_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    published = published_slugs()
    rows = [
        item for item in state.get("items") or []
        if isinstance(item, dict)
        and item.get("uploaded") is not True
        and item.get("status") in UNRESOLVED_STATUSES
        and (not published or source_slug(item) in published)
    ]
    return sorted(
        rows,
        key=lambda item: (
            source_date(item),
            str(item.get("created_at") or ""),
            str(item.get("id") or ""),
        ),
    )


def _mark_released(item: dict[str, Any], reason: str) -> None:
    item["status"] = RELEASED_STATUS
    item["uploaded"] = False
    item["release_reason"] = reason
    item["released_without_short_at"] = pipeline.utc_now()
    item["updated_at"] = pipeline.utc_now()


def release_without_short(slug: str, reason: str = "controller_bounded_release") -> int:
    """Persist a terminal no-Short result for one exact published article.

    If an item already exists, preserve its provider/upload identity as history
    but remove it from the unresolved FIFO. If no item exists, write a minimal
    tombstone containing the article source identity so future selection still
    treats this article as consumed.
    """
    slug = str(slug or "").strip()
    if not slug:
        raise pipeline.PipelineError("Release requires an exact article slug")
    source = current_source_snapshot(slug)
    state = pipeline.load_state()
    matches = [
        item
        for item in state.get("items") or []
        if isinstance(item, dict) and source_slug(item) == slug
    ]
    if matches:
        for item in matches:
            if item.get("uploaded") is True:
                # A public result already wins over a later release request.
                continue
            _mark_released(item, reason)
    else:
        state.setdefault("items", []).append({
            "id": f"short-release-{slug}-{source['content_sha256'][:10]}",
            "type": "short_release",
            "israel_date": pipeline.israel_now().date().isoformat(),
            "status": RELEASED_STATUS,
            "source": {
                key: value
                for key, value in source.items()
                if key not in {"body", "youtube_metadata"}
            },
            "uploaded": False,
            "release_reason": reason,
            "released_without_short_at": pipeline.utc_now(),
            "created_at": pipeline.utc_now(),
            "updated_at": pipeline.utc_now(),
        })
    pipeline.save_state(state)
    print(f"SHORT_RELEASED_WITHOUT_VIDEO slug={slug} reason={reason}")
    return 0


def is_recovery_mode() -> bool:
    if (os.environ.get("KESHER_RECOVERY_MODE") or "").lower().strip() in {"true", "1", "yes"}:
        return True
    if (os.environ.get("OPERATION") or "").lower().strip() in {"recovery", "reconcile"}:
        return True
    return False


def retry_technical_rejection(state: dict[str, Any], old: dict[str, Any]) -> dict[str, Any] | None:
    if not (old.get("status") == "rejected" and old.get("technical_verified") is not True):
        raise pipeline.PipelineError("Technical retry requested for a non-technical rejection")
    if is_recovery_mode():
        raise pipeline.PipelineError("RECOVERY_MODE_VIOLATION: retry_technical_rejection forbidden in same-identity recovery mode")
    slug = source_slug(old)
    if not slug:
        raise pipeline.PipelineError("Technical rejection has no source slug")
    source = current_source_snapshot(slug)
    if (old.get("source") or {}).get("content_sha256") != source["content_sha256"]:
        raise pipeline.PipelineError(
            f"Published source changed after video selection for {slug}"
        )
    recorded = old.get('fresh_generation_attempt', 1)
    if type(recorded) is not int or recorded < 1:
        raise pipeline.PipelineError('FRESH_GENERATION_ATTEMPT_INVALID')
    retries = max(int(old.get("technical_retry_count") or 0), recorded - 1)
    voice_rejection = (old.get('failure_signature') == 'wrong_narrator_gender'
                       or 'Detected male voice' in str((old.get('review_notes') or {}).get('technical', '')))
    if voice_rejection:
        policy = json.loads(pipeline.PRODUCTION_CONTRACT_FILE.read_text())['video']['voice_policy']
        if recorded >= int(policy['female_attempts_before_fallback']):
            if (policy['accept_male_on_final_female_attempt'] is True
                    and policy['fallback_voice_after_failed_female_attempts'] == 'male'
                    and old.get('raw_mp4') and old.get('task_id')):
                old['status'] = 'downloaded'
                old['voice_fallback_revalidation'] = True
                old['updated_at'] = pipeline.utc_now()
                return old  # same receipt, no fourth provider generation
            _mark_released(old, 'final_voice_attempt_has_no_recoverable_artifact')
            return None
    if retries >= MAX_TECHNICAL_RETRIES:
        _mark_released(old, "fresh_generation_budget_exhausted")
        return None

    old["status"] = "superseded"
    old["superseded_reason"] = "technical_retry_same_source"
    old["superseded_at"] = pipeline.utc_now()
    old["updated_at"] = pipeline.utc_now()

    replacement = pipeline.new_item(source)
    if old.get("type"):
        replacement["type"] = old["type"]
    if old.get("source_mode"):
        replacement["source_mode"] = old["source_mode"]
    replacement["technical_retry_count"] = retries + 1
    replacement["fresh_generation_attempt"] = retries + 2
    replacement["id"] += f"-a{retries + 2}"
    replacement["retry_of"] = old.get("id")
    state.setdefault("items", []).append(replacement)
    return replacement


def _has_valid_youtube_verification(item: dict[str, Any]) -> bool:
    if not bool(str(item.get("youtube_id") or "").strip()):
        return False
    ver = item.get("youtube_verification")
    if not isinstance(ver, dict):
        return False
    return bool(
        ver.get("channel_id") == pipeline.YOUTUBE_CHANNEL_ID
        and ver.get("privacy_status") == "public"
        and ver.get("processing_status") == "succeeded"
    )


def _short_item_canonical_origin_verified(item: dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    return delivery_guard._short_origin_verified(item)


def _short_media_and_signature_verified(item: dict[str, Any], source: dict[str, Any]) -> bool:
    if str((item.get("source") or {}).get("content_sha256") or "") != str(source.get("content_sha256") or ""):
        return False
    if not _short_item_canonical_origin_verified(item):
        return False
    media = item.get("media") or {}
    try:
        width = int(media.get("width") or 0)
        height = int(media.get("height") or 0)
    except (TypeError, ValueError):
        return False
    if width != 1080 or height != 1920 or height <= width:
        return False
    return delivery_guard._signature_verified(item)


def is_verified_public_short(item: dict[str, Any], source: dict[str, Any]) -> bool:
    if not _short_media_and_signature_verified(item, source):
        return False
    if not (item.get("uploaded") is True and item.get("status") == "uploaded"):
        return False
    return _has_valid_youtube_verification(item)


def is_uploaded_unverified_short(item: dict[str, Any], source: dict[str, Any]) -> bool:
    """Recognize an existing external Short identity without treating it as publication-safe.

    Legacy/external insertions may predate today's local provenance fields. They must
    block duplicate generation and be routed to remote verification, but they are not
    considered a verified public Short until the full canonical Short contract passes.
    """
    if not isinstance(item, dict) or item.get("type") != "article_short":
        return False
    if source_slug(item) != str(source.get("slug") or "").strip():
        return False
    if str((item.get("source") or {}).get("content_sha256") or "") != str(source.get("content_sha256") or ""):
        return False
    if not bool(str(item.get("youtube_id") or "").strip()):
        return False
    return not is_verified_public_short(item, source)


def is_verified_public_overview(item: dict[str, Any], source: dict[str, Any]) -> bool:
    if not isinstance(item, dict) or item.get("type") != "video_overview":
        return False
    if source_slug(item) != str(source.get("slug") or "").strip():
        return False
    if str((item.get("source") or {}).get("content_sha256") or "") != str(source.get("content_sha256") or ""):
        return False
    if not (item.get("uploaded") is True and item.get("status") == "uploaded"):
        return False
    return _has_valid_youtube_verification(item)


def is_uploaded_unverified_overview(item: dict[str, Any], source: dict[str, Any]) -> bool:
    if not isinstance(item, dict) or item.get("type") != "video_overview":
        return False
    if source_slug(item) != str(source.get("slug") or "").strip():
        return False
    if str((item.get("source") or {}).get("content_sha256") or "") != str(source.get("content_sha256") or ""):
        return False
    if not bool(str(item.get("youtube_id") or "").strip()):
        return False
    return not is_verified_public_overview(item, source)


def export_target(item: dict[str, Any] | None) -> None:
    if not isinstance(item, dict):
        return
    target_id = str(item.get("id") or "").strip()
    slug = source_slug(item)
    content_sha256 = str((item.get("source") or {}).get("content_sha256") or "").strip()
    if not target_id and not slug and not content_sha256:
        return
    env_path = os.environ.get("GITHUB_ENV")
    if env_path:
        try:
            with open(env_path, "a", encoding="utf-8") as f:
                if target_id:
                    f.write(f"TARGET_ITEM_ID={target_id}\n")
                if content_sha256:
                    f.write(f"TARGET_CONTENT_SHA256={content_sha256}\n")
                f.write(f"TARGET_GENERATION_ATTEMPT={item.get('fresh_generation_attempt', 1)}\n")
                if slug:
                    f.write(f"TARGET_SLUG={slug}\n")
        except OSError:
            pass


def _reconcile_item_technical_rejection(state: dict[str, Any], item: dict[str, Any]) -> None:
    if item.get("status") == "downloaded" and item.get("technical_verified") is not True:
        manifest_file = pipeline.STATE_DIR / f"{item.get('id')}-short-manifest.json"
        if manifest_file.exists():
            try:
                mdata = json.loads(manifest_file.read_text(encoding="utf-8"))
                if mdata.get("technical_verified") is False or mdata.get("rejection_reasons"):
                    item["status"] = "rejected"
                    item["rejected_at"] = pipeline.utc_now()
                    pipeline.save_state(state)
                    return
            except Exception:
                pass
        tech_note = str((item.get("review_notes") or {}).get("technical", "") or "")
        if tech_note.startswith("נפסל טכנית"):
            item["status"] = "rejected"
            item["rejected_at"] = pipeline.utc_now()
            pipeline.save_state(state)


def prepare_generation(target_slug: str = "") -> int:
    state = pipeline.load_state()
    target_slug = (target_slug or os.environ.get("TARGET_SLUG") or os.environ.get("DERIVE_SLUG") or "").strip()
    media_mode = (os.environ.get("KESHER_MEDIA_MODE") or "article_short").strip()
    if target_slug and media_mode == "video_overview":
        source = current_source_snapshot(target_slug)
        requested_sha = (os.environ.get("TARGET_CONTENT_SHA256") or "").strip()
        if requested_sha and requested_sha != source["content_sha256"]:
            raise pipeline.PipelineError(
                f"Published source changed after exact video request for {target_slug}"
            )
        requested_item_id = (os.environ.get("TARGET_ITEM_ID") or "").strip()
        same_source = [
            item for item in state.get("items") or []
            if isinstance(item, dict)
            and item.get("type") == "video_overview"
            and source_slug(item) == target_slug
            and str((item.get("source") or {}).get("content_sha256") or "") == source["content_sha256"]
        ]
        verified_public = [row for row in same_source if is_verified_public_overview(row, source)]
        uploaded_unverified = [row for row in same_source if is_uploaded_unverified_overview(row, source)]
        if verified_public or uploaded_unverified:
            chosen = verified_public[-1] if verified_public else uploaded_unverified[-1]
            modified = False
            for row in same_source:
                if (
                    row is not chosen
                    and row.get("uploaded") is not True
                    and not bool(str(row.get("youtube_id") or "").strip())
                    and row.get("status") in UNRESOLVED_STATUSES
                ):
                    row["status"] = "superseded"
                    row["superseded_reason"] = "already_public_same_source"
                    row["superseded_at"] = pipeline.utc_now()
                    row["updated_at"] = pipeline.utc_now()
                    modified = True
            if modified:
                pipeline.save_state(state)
            export_target(chosen)
            workflow_output("skip_generation", "true")
            if verified_public:
                print(f"VIDEO_GENERATION_ALREADY_PUBLIC slug={target_slug} item={chosen.get('id')}")
            else:
                print(f"VIDEO_GENERATION_UPLOAD_NEEDS_VERIFICATION slug={target_slug} item={chosen.get('id')}")
            return 0
        item = None
        if requested_item_id:
            exact = [row for row in same_source if str(row.get("id") or "") == requested_item_id]
            if len(exact) != 1:
                raise pipeline.PipelineError("EXACT_MEDIA_ITEM_ID_MISMATCH")
            item = exact[0]
            _reconcile_item_technical_rejection(state, item)

            is_voice_retry = (
                not is_recovery_mode()
                and item.get("status") == "rejected"
                and item.get("technical_verified") is not True
                and (
                    item.get("failure_signature") == "wrong_narrator_gender"
                    or "Detected male voice" in str((item.get("review_notes") or {}).get("technical", ""))
                )
                and int(item.get("fresh_generation_attempt") or 1) < 3
            )
            if is_voice_retry:
                replacement = retry_technical_rejection(state, item)
                pipeline.save_state(state)
                if replacement is None:
                    workflow_output("skip_generation", "true")
                    print(
                        "VIDEO_RECONCILED_GENERATION "
                        f"slug={target_slug} released_without_video=yes"
                    )
                    return 0
                export_target(replacement)
                workflow_output("skip_generation", "false")
                print(
                    "VIDEO_RECONCILED_GENERATION "
                    f"slug={target_slug} technical_retry=yes "
                    f"attempt={replacement.get('fresh_generation_attempt', 1)}"
                )
                return 0

            export_target(item)
            # Recovery mode semantics for exact existing item:
            # source_selected / source_added -> continue provider generation for the SAME item (skip_generation=false)
            # generating -> poll existing provider task only (skip_generation=false)
            # downloaded -> continue local post-processing/render/validation for SAME item (skip_generation=false)
            # approved / pending_review / verified -> proceed toward exact upload (skip_generation=true)
            # uploaded -> reconciliation only; never upload again (skip_generation=true)
            # rejected -> obey explicit final fallback/recovery policy; never silently fresh-generate (skip_generation=true)
            if item.get("status") in PROVIDER_PROGRESS_STATUSES:
                workflow_output("skip_generation", "false")
                print(
                    "VIDEO_RECONCILED_GENERATION "
                    f"slug={target_slug} recovery_advance_local=yes item={item.get('id')} status={item.get('status')}"
                )
                return 0
            workflow_output("skip_generation", "true")
            print(
                "VIDEO_RECONCILED_GENERATION "
                f"slug={target_slug} recovery_skip_generation=yes item={item.get('id')} status={item.get('status')}"
            )
            return 0

        unresolved = [
            row for row in same_source
            if row.get("uploaded") is not True and row.get("status") in UNRESOLVED_STATUSES
        ]
        if len(unresolved) > 1:
            raise pipeline.PipelineError(
                "More than one exact Video Overview is unresolved; EXACT_MEDIA_ITEM_ID_REQUIRED"
            )
        item = unresolved[0] if unresolved else None
        if item is not None:
            _reconcile_item_technical_rejection(state, item)
            export_target(item)
            if item.get("status") == "rejected" and item.get("technical_verified") is not True:
                replacement = retry_technical_rejection(state, item)
                pipeline.save_state(state)
                if replacement is None:
                    workflow_output("skip_generation", "true")
                    print(
                        "VIDEO_RECONCILED_GENERATION "
                        f"slug={target_slug} released_without_video=yes"
                    )
                    return 0
                export_target(replacement)
                workflow_output("skip_generation", "false")
                print(
                    "VIDEO_RECONCILED_GENERATION "
                    f"slug={target_slug} technical_retry=yes "
                    f"attempt={replacement.get('fresh_generation_attempt', 1)}"
                )
                return 0
            workflow_output("skip_generation", "false")
            print(
                "VIDEO_RECONCILED_GENERATION "
                f"slug={target_slug} backlog_resume=yes status={item.get('status')}"
            )
            return 0
        workflow_output("skip_generation", "false")
        print(
            "VIDEO_RECONCILED_GENERATION "
            f"slug={target_slug} targeted_long_defer_to_pipeline=yes"
        )
        return 0
    if target_slug:
        source = current_source_snapshot(target_slug)
        same_source = [
            item for item in state.get("items") or []
            if isinstance(item, dict) and source_slug(item) == target_slug
        ]
        verified_public = [
            item for item in same_source
            if is_verified_public_short(item, source)
        ]
        uploaded_unverified = [
            item for item in same_source
            if is_uploaded_unverified_short(item, source)
        ]
        if verified_public or uploaded_unverified:
            chosen = verified_public[-1] if verified_public else uploaded_unverified[-1]
            modified = False
            for item in same_source:
                if (
                    item is not chosen
                    and item.get("uploaded") is not True
                    and not bool(str(item.get("youtube_id") or "").strip())
                    and item.get("status") in UNRESOLVED_STATUSES
                ):
                    item["status"] = "superseded"
                    item["superseded_reason"] = "already_public_same_source"
                    item["superseded_at"] = pipeline.utc_now()
                    item["updated_at"] = pipeline.utc_now()
                    modified = True
            if modified:
                pipeline.save_state(state)
            export_target(chosen)
            workflow_output("skip_generation", "true")
            if verified_public:
                print(f"SHORT_GENERATION_ALREADY_PUBLIC slug={target_slug} item={chosen.get('id')}")
            else:
                print(f"SHORT_GENERATION_UPLOAD_NEEDS_VERIFICATION slug={target_slug} item={chosen.get('id')}")
            return 0

        # A targeted recovery must follow the currently published article identity.
        # Stale unresolved work for the same slug belongs to the previous content SHA and
        # must not be retried against the new source.
        for item in same_source:
            item_sha = str((item.get("source") or {}).get("content_sha256") or "")
            if (
                item_sha
                and item_sha != source["content_sha256"]
                and item.get("uploaded") is not True
                and item.get("status") in UNRESOLVED_STATUSES
            ):
                item["status"] = "superseded"
                item["superseded_reason"] = "published_source_changed"
                item["superseded_at"] = pipeline.utc_now()
                item["updated_at"] = pipeline.utc_now()
                continue
            if (
                item.get("uploaded") is True
                and not is_verified_public_short(item, source)
                and not is_uploaded_unverified_short(item, source)
            ):
                item["status"] = "superseded"
                item["superseded_reason"] = "unverified_or_legacy_short"
                item["uploaded"] = False
            elif item.get("source_mode") == "overview-segment":
                item["status"] = "superseded"
                item["superseded_reason"] = "forbidden_overview_segment"
                item["uploaded"] = False

        unresolved = [
            item for item in same_source
            if item.get("uploaded") is not True and item.get("status") in UNRESOLVED_STATUSES
        ]
        if unresolved:
            item = unresolved[0]
            _reconcile_item_technical_rejection(state, item)
            export_target(item)
            if item.get("status") == "rejected" and item.get("technical_verified") is not True:
                replacement = retry_technical_rejection(state, item)
                pipeline.save_state(state)
                if replacement is None:
                    workflow_output("skip_generation", "true")
                    print(
                        "VIDEO_RECONCILED_GENERATION "
                        f"slug={target_slug} released_without_short=yes fresh_attempts=4"
                    )
                    return 0
                export_target(replacement)
                print(
                    "VIDEO_RECONCILED_GENERATION "
                    f"slug={target_slug} technical_retry=yes"
                )
                return 0
            print(
                "VIDEO_RECONCILED_GENERATION "
                f"slug={target_slug} backlog_resume=yes status={item.get('status')}"
            )
            return 0

        item = pipeline.new_item(source)
        item["type"] = "article_short"
        item["source_mode"] = "direct-short"
        item["fresh_generation_attempt"] = 1
        state.setdefault("items", []).append(item)
        pipeline.save_state(state)
        export_target(item)
        print(f"VIDEO_RECONCILED_GENERATION slug={target_slug} initialized=yes")
        return 0

    existing = unresolved_items(state)
    if existing:
        item = existing[0]
        _reconcile_item_technical_rejection(state, item)
        export_target(item)
        if item.get("status") == "rejected" and item.get("technical_verified") is not True:
            replacement = retry_technical_rejection(state, item)
            pipeline.save_state(state)
            if replacement is None:
                workflow_output("skip_generation", "true")
                print(
                    "VIDEO_RECONCILED_GENERATION "
                    f"slug={source_slug(item)} released_without_short=yes fresh_attempts=4"
                )
                return 0
            export_target(replacement)
            print(
                "VIDEO_RECONCILED_GENERATION "
                f"slug={source_slug(replacement)} technical_retry=yes backlog_size={len(existing)}"
            )
            return 0
        print(
            "VIDEO_RECONCILED_GENERATION "
            f"slug={source_slug(item)} backlog_resume=yes status={item.get('status')} backlog_size={len(existing)}"
        )
        return 0

    source = authoritative_article()
    print(
        "VIDEO_RECONCILED_GENERATION "
        f"slug={source['slug']} backlog_resume=no technical_retry=no"
    )
    return 0


def technical_publication_ready(item: dict[str, Any]) -> bool:
    policy = load_policy()
    video_policy = policy["video"]
    if video_policy.get("publication_gate") != "technical" or video_policy.get("jules_is_advisory") is not True:
        raise pipeline.PipelineError("Video policy no longer declares technical publication with advisory Jules review")
    if not isinstance(item, dict):
        return False
    item_type = item.get("type")
    if item_type in {"video_overview", None}:
        return bool(
            pipeline.can_long_item_proceed_toward_publication(item)
            and item.get("final_sha256")
        )
    elif item_type == "article_short":
        return bool(
            pipeline.can_short_item_proceed_toward_publication(item)
            and item.get("final_sha256")
        )
    return False


def recover_persisted_youtube_id(state: dict[str, Any], item: dict[str, Any]) -> bool:
    """Finish public verification after an earlier upload already returned its ID."""
    if not bool(str(item.get("youtube_id") or "").strip()):
        return False
    if item.get("uploaded") is True and _has_valid_youtube_verification(item):
        return False
    token = pipeline.youtube_access_token()
    pipeline.verify_authenticated_channel(token)
    try:
        verification = pipeline.verify_public_upload(item, token)
    except pipeline.PipelineError as exc:
        if not str(exc).startswith("PUBLIC_METADATA_INVALID: remote "):
            raise
        try:
            pipeline.repair_persisted_youtube_metadata(item, token)
        except pipeline.PipelineError as repair_exc:
            if "HTTP 403" not in str(repair_exc):
                raise
            print("WARNING: YouTube metadata repair returned HTTP 403 (upload token scope insufficient for video.update); continuing to verification...")
        verification = pipeline.verify_public_upload(item, token)
    item["youtube_verification"] = verification
    item["youtube_url"] = f"https://www.youtube.com/watch?v={item['youtube_id']}"
    item["uploaded"] = True
    item["status"] = "uploaded"
    item["uploaded_at"] = pipeline.utc_now()
    item["updated_at"] = pipeline.utc_now()
    pipeline.save_state(state)
    print(
        "VIDEO_YOUTUBE_ID_RECOVERED "
        f"item={item.get('id')} youtube_id={item.get('youtube_id')}"
    )
    return True


def prepare_upload(
    target_slug: str | None = None,
    content_sha256: str | None = None,
    item_id: str | None = None,
) -> int:
    state = pipeline.load_state()
    unresolved = unresolved_items(state)
    target_item_id = (
        item_id
        or os.environ.get("TARGET_ITEM_ID")
        or os.environ.get("KESHER_REQUESTED_TARGET_ITEM_ID")
        or ""
    ).strip()
    target_content_sha256 = (
        content_sha256
        or os.environ.get("KESHER_REQUESTED_TARGET_CONTENT_SHA256")
        or os.environ.get("TARGET_CONTENT_SHA256")
        or ""
    ).strip()
    target = (
        target_slug
        or os.environ.get("KESHER_REQUESTED_TARGET_SLUG")
        or os.environ.get("TARGET_SLUG")
        or os.environ.get("DERIVE_SLUG")
        or ""
    ).strip()
    exact_required = (os.environ.get("KESHER_EXACT_UPLOAD_REQUIRED") or "").strip().lower() == "true"
    media_mode = os.environ.get('KESHER_MEDIA_MODE', '')
    reconciled_predecessor_item_id = (os.environ.get("KESHER_REQUESTED_TARGET_ITEM_ID") or "").strip()
    if reconciled_predecessor_item_id == target_item_id:
        reconciled_predecessor_item_id = ""
    target_candidates = [
        i for i in state.get("items", [])
        if isinstance(i, dict) and str(i.get("id") or "").strip() == target_item_id
    ] if target_item_id else []
    is_target_short = any(i.get("type") == "article_short" for i in target_candidates) or media_mode == "article_short"
    overview = (media_mode == 'video_overview' or (media_mode != 'article_short'
                and any(item.get('type') == 'video_overview' for item in state.get('items', [])))) and not is_target_short
    exact_requested = overview or exact_required or bool(target_item_id or target_content_sha256)
    if exact_requested:
        if not all((target, target_content_sha256, target_item_id)):
            raise pipeline.PipelineError(
                "Exact identity lock requires target_slug, content_sha256, and target_item_id"
            )

        if target_item_id and pipeline.STATE_FILE.is_file():
            auth_state = pipeline.load_state()
            auth_items_by_id = {
                str(r.get("id")): r
                for r in auth_state.get("items", [])
                if isinstance(r, dict)
            }
            if str(target_item_id).strip() not in auth_items_by_id:
                workflow_output("ready", "false")
                raise pipeline.PipelineError(
                    f"AUTHORITATIVE_ITEM_MISSING: item {target_item_id} absent from authoritative state on disk"
                )
            target_auth = auth_items_by_id[str(target_item_id).strip()]
            if target_auth.get("uploaded") is True and bool(str(target_auth.get("youtube_id") or "").strip()):
                export_target(target_auth)
                workflow_output("ready", "false")
                print(f"VIDEO_RECONCILED_UPLOAD candidate=already_public slug={target or source_slug(target_auth)} item={target_auth.get('id')}")
                return 0

        from scripts import kesher_final_attempt_fallback as fallback
        if overview:
            if target_candidates and target_candidates[0].get("final_attempt_fallback") is True and not fallback.is_fallback_promotion_enabled():
                workflow_output("ready", "false")
                raise pipeline.PipelineError(
                    "FALLBACK_WINNER_AUTHORITY_UNAVAILABLE: fallback publication is disabled"
                )

            try:
                authoritative_item = pipeline.verify_single_upload_authority(
                    state, target, target_content_sha256, target_item_id, candidate_items=unresolved,
                    reconciled_predecessor_item_id=reconciled_predecessor_item_id,
                )
            except pipeline.PipelineError:
                workflow_output("ready", "false")
                raise

            if authoritative_item.get("uploaded") is True and bool(str(authoritative_item.get("youtube_id") or "").strip()):
                export_target(authoritative_item)
                workflow_output("ready", "false")
                print(f"VIDEO_RECONCILED_UPLOAD candidate=already_public slug={target} item={authoritative_item.get('id')}")
                return 0

            if state.get("fallback_winner"):
                fw = state["fallback_winner"]
                if fw.get("slug") == target and fw.get("content_sha256") == target_content_sha256:
                    if fw.get("fallback_committed") is True and fw.get("winner_item_id") != target_item_id:
                        workflow_output("ready", "false")
                        raise pipeline.PipelineError(
                            f"EXACT_UPLOAD_SUPERSEDED: item {target_item_id} superseded by fallback winner {fw.get('winner_item_id')}"
                        )
        exact = [
            item for item in unresolved
            if str(item.get("id") or "").strip() == target_item_id
            and source_slug(item) == target
            and str((item.get("source") or {}).get("content_sha256") or "").strip() == target_content_sha256
        ]
        if exact and (exact[0].get("status") == "superseded" or exact[0].get("upload_eligible") is False):
            workflow_output("ready", "false")
            raise pipeline.PipelineError(
                f"EXACT_UPLOAD_SUPERSEDED: item {target_item_id} is superseded"
            )
        if len(exact) != 1:
            exact_all = [
                item for item in state.get("items") or []
                if isinstance(item, dict)
                and str(item.get("id") or "").strip() == target_item_id
                and source_slug(item) == target
                and str((item.get("source") or {}).get("content_sha256") or "").strip() == target_content_sha256
            ]
            if len(exact_all) == 1:
                matched_item = exact_all[0]
                if matched_item.get("uploaded") is True and bool(str(matched_item.get("youtube_id") or "").strip()):
                    export_target(matched_item)
                    workflow_output("ready", "false")
                    print(f"VIDEO_RECONCILED_UPLOAD candidate=already_public slug={target} item={matched_item.get('id')}")
                    return 0
                if bool(str(matched_item.get("youtube_id") or "").strip()):
                    export_target(matched_item)
                    if recover_persisted_youtube_id(state, matched_item):
                        workflow_output("ready", "false")
                        return 0
                if matched_item.get("status") == RELEASED_STATUS:
                    workflow_output("ready", "false")
                    print("VIDEO_RECONCILED_UPLOAD candidate=none")
                    return 0
            raise pipeline.PipelineError(
                "Exact identity lock did not match exactly one unresolved video item"
            )
        if overview:
            pipeline.existing_item(state, target_item_id, target, target_content_sha256, kind='overview')
        unresolved = exact
    elif target:
        unresolved = [item for item in unresolved if source_slug(item) == target]
        if not unresolved:
            same_slug_items = [
                item for item in state.get("items") or []
                if isinstance(item, dict) and source_slug(item) == target
            ]
            unverified_with_yt = [
                item for item in same_slug_items
                if bool(str(item.get("youtube_id") or "").strip()) and not _has_valid_youtube_verification(item)
            ]
            if unverified_with_yt:
                candidate = unverified_with_yt[-1]
                export_target(candidate)
                if recover_persisted_youtube_id(state, candidate):
                    workflow_output("ready", "false")
                    return 0
            verified_with_yt = [
                item for item in same_slug_items
                if item.get("uploaded") is True and _has_valid_youtube_verification(item)
            ]
            if verified_with_yt:
                export_target(verified_with_yt[-1])
                workflow_output("ready", "false")
                print(f"VIDEO_RECONCILED_UPLOAD candidate=already_public slug={target} item={verified_with_yt[-1].get('id')}")
                return 0
    if not unresolved:
        workflow_output("ready", "false")
        print("VIDEO_RECONCILED_UPLOAD candidate=none")
        return 0

    item = unresolved[0]
    export_target(item)
    cand_slug = source_slug(item)
    cand_hash = str((item.get("source") or {}).get("content_sha256") or "").strip()
    item_type = item.get("type")
    if item_type not in {"video_overview", "article_short", None}:
        workflow_output("ready", "false")
        raise pipeline.PipelineError(f"UNKNOWN_MEDIA_TYPE: unsupported media item type '{item_type}'")

    is_short = item_type == "article_short"
    is_long = item_type in {"video_overview", None}

    if is_long:
        from scripts import kesher_final_attempt_fallback as fallback
        if item.get("final_attempt_fallback") is True and not fallback.is_fallback_promotion_enabled():
            workflow_output("ready", "false")
            raise pipeline.PipelineError(
                "FALLBACK_WINNER_AUTHORITY_UNAVAILABLE: fallback publication is disabled"
            )
        if cand_slug and cand_hash:
            try:
                authoritative_item = pipeline.verify_single_upload_authority(
                    state, cand_slug, cand_hash, item.get("id"), candidate_items=unresolved,
                    reconciled_predecessor_item_id=reconciled_predecessor_item_id,
                )
            except pipeline.PipelineError:
                workflow_output("ready", "false")
                raise
            item = authoritative_item
            if isinstance(state.get("items"), list):
                for idx, existing in enumerate(state["items"]):
                    if isinstance(existing, dict) and str(existing.get("id") or "").strip() == str(item.get("id") or "").strip():
                        state["items"][idx] = item
                        break
            export_target(item)
    elif is_short:
        if pipeline.STATE_FILE.is_file():
            auth_state = pipeline.load_state()
            auth_item = next((r for r in auth_state.get("items", []) if str(r.get("id") or "").strip() == str(item.get("id") or "").strip()), None)
            if auth_item is not None:
                item = auth_item
                if isinstance(state.get("items"), list):
                    for idx, existing in enumerate(state["items"]):
                        if isinstance(existing, dict) and str(existing.get("id") or "").strip() == str(item.get("id") or "").strip():
                            state["items"][idx] = item
                            break
            if auth_item and (auth_item.get("status") == "superseded" or auth_item.get("upload_eligible") is False):
                workflow_output("ready", "false")
                raise pipeline.PipelineError(f"EXACT_UPLOAD_SUPERSEDED: item {item.get('id')} is superseded")
    export_target(item)

    if item.get("uploaded") is True and bool(str(item.get("youtube_id") or "").strip()):
        workflow_output("ready", "false")
        print(f"VIDEO_RECONCILED_UPLOAD candidate=already_public slug={cand_slug} item={item.get('id')}")
        return 0

    if bool(str(item.get("youtube_id") or "").strip()) and not (item.get("uploaded") is True and _has_valid_youtube_verification(item)):
        if recover_persisted_youtube_id(state, item):
            workflow_output("ready", "false")
            return 0

    if not technical_publication_ready(item):
        # Provider progress is not a failed publication attempt. Preserve the
        # exact provider IDs and let the next poll resume the same task.
        if item.get("status") in PROVIDER_PROGRESS_STATUSES and item.get("technical_verified") is not True:
            workflow_output("ready", "false")
            print(
                "VIDEO_RECONCILED_UPLOAD candidate=pending "
                f"slug={source_slug(item)} status={item.get('status')} "
                f"task_id={item.get('task_id') or 'none'}"
            )
            return 0
        if item.get("status") == "rejected" and item.get("technical_verified") is not True:
            workflow_output("ready", "false")
            print(
                "VIDEO_RECONCILED_UPLOAD candidate=rejected "
                f"slug={source_slug(item)} status={item.get('status')} "
                f"reasons={item.get('review_notes', {}).get('technical') or 'unknown'}"
            )
            return 0
        raise pipeline.PipelineError(
            "Oldest unresolved video is not technically verified for publication"
        )

    if item.get("source_mode") == "overview-segment":
        workflow_output("ready", "false")
        print(
            "VIDEO_RECONCILED_UPLOAD candidate=rejected "
            f"slug={source_slug(item)} status={item.get('status')} "
            "reasons=forbidden_overview_segment"
        )
        return 0

    slug = source_slug(item)
    source = current_source_snapshot(slug)
    if (item.get("source") or {}).get("content_sha256") != source["content_sha256"]:
        raise pipeline.PipelineError(
            f"Published source changed before upload for {slug}"
        )

    if is_long and reconciled_predecessor_item_id:
        for predecessor in state.get("items", []) or []:
            if (
                isinstance(predecessor, dict)
                and str(predecessor.get("id") or "").strip() == reconciled_predecessor_item_id
                and source_slug(predecessor) == cand_slug
                and str((predecessor.get("source") or {}).get("content_sha256") or "").strip() == cand_hash
                and predecessor.get("uploaded") is not True
            ):
                predecessor["status"] = "superseded"
                predecessor["superseded_reason"] = "reconciled_target_replacement"
                predecessor["superseded_at"] = pipeline.utc_now()
                predecessor["updated_at"] = pipeline.utc_now()

    prior_status = item.get("status")
    item["review_gate"] = "advisory-jules"
    item["advisory_review_status_before_upload"] = prior_status
    if prior_status not in {"approved", "uploading"}:
        item["status"] = "approved"
    item["updated_at"] = pipeline.utc_now()
    try:
        validate_upload_candidate(item)
    except Exception as exc:
        raise pipeline.PipelineError(f"Exact-evidence upload guard rejected candidate: {exc}") from exc
    pipeline.save_state(state)
    workflow_output("ready", "true")
    print(
        "VIDEO_RECONCILED_UPLOAD "
        f"slug={slug} item={item.get('id')} gate=technical jules=advisory exact_evidence=yes"
    )
    return 0



def adopt_long_form_provider(state_path: str, slug: str, content_sha256: str, long_item_id: str) -> int:
    """Seed/resume one Short from an already-published long-form provider identity.

    This path never calls NotebookLM generation. It only copies the exact durable
    provider identity into Short state, after verifying the current article and
    the long-form public YouTube evidence.
    """
    slug = str(slug or "").strip()
    content_sha256 = str(content_sha256 or "").strip()
    long_item_id = str(long_item_id or "").strip()
    if not slug or not content_sha256 or not long_item_id:
        raise pipeline.PipelineError("Short derive requires slug, content hash and long-form item id")

    source = current_source_snapshot(slug)
    if str(source.get("content_sha256") or "") != content_sha256:
        raise pipeline.PipelineError(f"Published source hash changed before Short derive for {slug}")

    path = Path(state_path)
    if not path.is_file():
        raise pipeline.PipelineError("Long-form durable state is missing for Short derive")
    long_state = json.loads(path.read_text(encoding="utf-8"))
    if long_state.get("version") != 1 or not isinstance(long_state.get("items"), list):
        raise pipeline.PipelineError("Long-form durable state schema is unsupported")

    matches = [
        item for item in long_state["items"]
        if isinstance(item, dict)
        and str(item.get("id") or "") == long_item_id
        and source_slug(item) == slug
        and str((item.get("source") or {}).get("content_sha256") or "") == content_sha256
    ]
    if len(matches) != 1:
        raise pipeline.PipelineError("Exact long-form provider item was not found uniquely")
    long_item = matches[0]
    verification = long_item.get("youtube_verification") or {}
    if not (
        long_item.get("uploaded") is True
        and long_item.get("status") == "uploaded"
        and long_item.get("youtube_id")
        and verification.get("channel_id") == pipeline.YOUTUBE_CHANNEL_ID
        and verification.get("privacy_status") == "public"
        and verification.get("processing_status") == "succeeded"
    ):
        raise pipeline.PipelineError("Long-form provider item is not authoritatively public")

    source_id = str(long_item.get("source_id") or "").strip()
    task_id = str(long_item.get("task_id") or "").strip()
    artifact_id = str(long_item.get("artifact_id") or "").strip()
    if not source_id or not task_id or not artifact_id or task_id != artifact_id:
        raise pipeline.PipelineError("Long-form provider identity is incomplete")

    state = pipeline.load_state()
    published = published_slugs()
    if published:
        for row in state.get("items") or []:
            if isinstance(row, dict) and source_slug(row) not in published and row.get("status") in UNRESOLVED_STATUSES:
                row["status"] = "superseded"
                row["superseded_reason"] = "unpublished_article_draft"
                row["updated_at"] = pipeline.utc_now()
    same_source = [
        item for item in state.get("items") or []
        if isinstance(item, dict)
        and source_slug(item) == slug
        and str((item.get("source") or {}).get("content_sha256") or "") == content_sha256
    ]
    uploaded = [item for item in same_source if item.get("uploaded") is True and item.get("status") == "uploaded"]
    if uploaded:
        workflow_output("skip_generation", "true")
        print(f"SHORT_DERIVE_ALREADY_PUBLIC slug={slug} item={uploaded[-1].get('id')}")
        return 0

    workflow_output("skip_generation", "false")
    unresolved = [item for item in same_source if item.get("uploaded") is not True and item.get("status") in UNRESOLVED_STATUSES]
    if len(unresolved) > 1:
        raise pipeline.PipelineError("More than one unresolved Short exists for derived source")
    if unresolved:
        item = unresolved[0]
        existing_identity = (
            str(item.get("source_id") or ""),
            str(item.get("task_id") or ""),
            str(item.get("artifact_id") or ""),
        )
        if any(existing_identity) and existing_identity != (source_id, task_id, artifact_id):
            raise pipeline.PipelineError("Existing Short provider identity differs from long-form source")
        item.update({
            "source_id": source_id,
            "task_id": task_id,
            "artifact_id": artifact_id,
            "adopted_from_long_item_id": long_item_id,
            "shared_provider_identity": True,
            "updated_at": pipeline.utc_now(),
        })
        if item.get("status") in {"source_selected", "source_added"}:
            item["status"] = "generating"
        pipeline.save_state(state)
        print(f"SHORT_DERIVE_RESUMED slug={slug} item={item.get('id')} long_item={long_item_id}")
        return 0

    item = pipeline.new_item(source)
    item.update({
        "type": "article_short",
        "source_mode": "overview-segment",
        "fresh_generation_attempt": 0,
        "status": "generating",
        "source_id": source_id,
        "task_id": task_id,
        "artifact_id": artifact_id,
        "adopted_from_long_item_id": long_item_id,
        "shared_provider_identity": True,
    })
    state.setdefault("items", []).append(item)
    pipeline.save_state(state)
    print(f"SHORT_DERIVE_ADOPTED slug={slug} item={item.get('id')} long_item={long_item_id}")
    return 0


def bind_short_overview_identity(
    long_state_path: str,
    slug: str,
    content_sha256: str,
    long_item_id: str,
    short_item_id: str = "",
) -> int:
    """Persist exact authoritative Overview provenance onto an existing native Short.

    This is recovery metadata only. It never copies Long provider IDs into the Short's
    own provider identity and never generates, renders, uploads, or replaces media.
    """
    slug = str(slug or "").strip()
    content_sha256 = str(content_sha256 or "").strip()
    long_item_id = str(long_item_id or "").strip()
    short_item_id = str(short_item_id or "").strip()
    if not slug or not content_sha256 or not long_item_id:
        raise pipeline.PipelineError("Short Overview binding requires slug, content hash and long item id")

    source = current_source_snapshot(slug)
    if str(source.get("content_sha256") or "") != content_sha256:
        raise pipeline.PipelineError(f"Published source hash changed before Short Overview binding for {slug}")

    path = Path(long_state_path)
    if not path.is_file():
        raise pipeline.PipelineError("Authoritative Overview state artifact is missing")
    long_state = json.loads(path.read_text(encoding="utf-8"))
    if long_state.get("version") != 1 or not isinstance(long_state.get("items"), list):
        raise pipeline.PipelineError("Authoritative Overview state schema is unsupported")

    long_matches = [
        row for row in long_state["items"]
        if isinstance(row, dict)
        and str(row.get("id") or "").strip() == long_item_id
        and row.get("type") == "video_overview"
        and source_slug(row) == slug
        and str((row.get("source") or {}).get("content_sha256") or "").strip() == content_sha256
    ]
    if len(long_matches) != 1:
        raise pipeline.PipelineError("Exact authoritative Overview item was not found uniquely")
    long_item = long_matches[0]
    verification = long_item.get("youtube_verification") or {}
    if not (
        long_item.get("technical_verified") is True
        and long_item.get("uploaded") is True
        and long_item.get("status") == "uploaded"
        and bool(str(long_item.get("youtube_id") or "").strip())
        and verification.get("channel_id") == pipeline.YOUTUBE_CHANNEL_ID
        and verification.get("privacy_status") == "public"
        and verification.get("processing_status") == "succeeded"
    ):
        raise pipeline.PipelineError("Exact authoritative Overview item is not verified public")

    identity_fields = ("notebook_id", "source_id", "task_id", "artifact_id", "raw_sha256")
    overview_identity = {field: str(long_item.get(field) or "").strip() for field in identity_fields}
    if any(not overview_identity[field] for field in identity_fields):
        raise pipeline.PipelineError("Exact authoritative Overview provider identity is incomplete")
    raw_sha = overview_identity["raw_sha256"]
    if len(raw_sha) != 64 or any(ch not in "0123456789abcdef" for ch in raw_sha.lower()):
        raise pipeline.PipelineError("Exact authoritative Overview raw SHA is invalid")

    state = pipeline.load_state()
    candidates = [
        row for row in state.get("items", [])
        if isinstance(row, dict)
        and row.get("type") == "article_short"
        and source_slug(row) == slug
        and str((row.get("source") or {}).get("content_sha256") or "").strip() == content_sha256
        and row.get("status") != "superseded"
        and (not short_item_id or str(row.get("id") or "").strip() == short_item_id)
    ]
    if len(candidates) != 1:
        raise pipeline.PipelineError("Exact native Short item was not found uniquely for Overview binding")
    short_item = candidates[0]
    if short_item.get("uploaded") is True:
        raise pipeline.PipelineError("Refusing to mutate already-uploaded Short provenance")
    if short_item.get("status") in {"generating", "source_selected", "source_added"} or not short_item.get("raw_sha256"):
        raise pipeline.PipelineError(
            f"Cannot bind Overview identity: Short item {short_item.get('id')} is still {short_item.get('status')}"
        )

    existing = short_item.get("overview_provider_identity")
    if existing is not None and existing != overview_identity:
        raise pipeline.PipelineError("Existing Short Overview identity conflicts with authoritative Overview")

    short_item["overview_provider_identity"] = overview_identity
    if not delivery_guard._short_origin_verified(short_item):
        short_item.pop("overview_provider_identity", None)
        raise pipeline.PipelineError("Authoritative Overview identity does not prove independent Short origin")
    short_item["updated_at"] = pipeline.utc_now()
    pipeline.save_state(state)
    export_target(short_item)
    print(
        "SHORT_OVERVIEW_IDENTITY_BOUND "
        f"slug={slug} short_item={short_item.get('id')} long_item={long_item_id}"
    )
    return 0

def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-generation", action="store_true")
    mode.add_argument("--prepare-upload", action="store_true")
    mode.add_argument("--release-without-short", metavar="SLUG")
    mode.add_argument("--adopt-long-form-state", metavar="STATE_PATH")
    mode.add_argument("--bind-short-overview-identity", metavar="STATE_PATH")
    parser.add_argument("--slug", default="")
    parser.add_argument("--content-sha256", default="")
    parser.add_argument("--item-id", default="")
    parser.add_argument("--long-item-id", default="")
    args = parser.parse_args()
    if args.prepare_generation:
        return prepare_generation(args.slug)
    if args.prepare_upload:
        return prepare_upload(args.slug, args.content_sha256, args.item_id)
    if args.adopt_long_form_state:
        return adopt_long_form_provider(args.adopt_long_form_state, args.slug, args.content_sha256, args.long_item_id)
    if args.bind_short_overview_identity:
        return bind_short_overview_identity(
            args.bind_short_overview_identity, args.slug, args.content_sha256, args.long_item_id, args.item_id
        )
    return release_without_short(str(args.release_without_short))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (pipeline.PipelineError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"VIDEO_RECONCILE_BLOCKED {exc}")
        raise SystemExit(1)