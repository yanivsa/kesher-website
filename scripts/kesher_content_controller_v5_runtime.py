#!/usr/bin/env python3
"""Production runtime activation plus exact prior-cycle media recovery."""

from __future__ import annotations

import copy
import sys

if __package__:
    from . import kesher_content_controller_v5 as v5
    from . import kesher_content_controller_v5_runtime_base as base_runtime
    from . import kesher_e2e_delivery_guard as delivery_guard
    from . import kesher_three_strike_runtime as three_strike
else:
    import kesher_content_controller_v5 as v5
    import kesher_content_controller_v5_runtime_base as base_runtime
    import kesher_e2e_delivery_guard as delivery_guard
    import kesher_three_strike_runtime as three_strike

ARTICLE_AUTO_MERGE_WORKFLOW = base_runtime.ARTICLE_AUTO_MERGE_WORKFLOW
MEDIA_WATCHDOG_STATUSES = base_runtime.MEDIA_WATCHDOG_STATUSES
DEFAULT_SIGNATURE_ASSET = "public/images/signature/signature-mask.svg"
BACKLOG_MEDIA_RECOVERY_WORKFLOW = "kesher-backlog-media-recovery.yml"
MAX_BACKLOG_SEED_DISPATCHES = 3
MAX_BACKLOG_SHORT_DISPATCHES = 4
MAX_BACKLOG_EVIDENCE_REBUILDS = 2
MAX_BACKLOG_DEPLOY_DISPATCHES = 3
IMMUTABLE_EVIDENCE_HASHES = (
    "manifest_sha256",
    "transcript_sha256",
    "source_file_sha256",
    "visual_review_sha256",
)
TERMINAL_BACKLOG_MEDIA_ERRORS = frozenset({
    "BACKLOG_SHORT_ATTEMPTS_EXHAUSTED",
    "BACKLOG_EXACT_SEED_ATTEMPTS_EXHAUSTED",
    "BACKLOG_LEGACY_EVIDENCE_REBUILD_EXHAUSTED",
})


def legacy_immutable_evidence_gap(item):
    """True only for publication-ready legacy items missing the current evidence contract."""
    if not isinstance(item, dict) or item.get("uploaded") is True:
        return False
    if item.get("technical_verified") is not True:
        return False
    if str(item.get("status") or "") not in {"pending_review", "approved", "rejected", "uploading"}:
        return False
    if any(not item.get(field) for field in IMMUTABLE_EVIDENCE_HASHES):
        return True
    frame_hashes = item.get("frame_sha256")
    return not isinstance(frame_hashes, dict) or not frame_hashes


def ordered_recoverable_backlog(rows):
    """Return newest-first backlog rows that may still make autonomous progress.

    A terminally exhausted or quarantined historical row remains in state for
    supervisor/direct takeover, but it must never starve a fresher recoverable
    delivery or crash the current controller tick.
    """
    recoverable = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        media = row.get("media") or {}
        if media.get("complete") is True:
            continue
        if (
            media.get("quarantined") is True
            or str(row.get("status") or "") == "quarantined_ambiguous_identity"
            or str(media.get("status") or "") == "quarantined_ambiguous_identity"
            or str(media.get("long_status") or "") == "quarantined_ambiguous_identity"
        ):
            continue
        last_error = str(media.get("last_error") or "")
        if last_error in TERMINAL_BACKLOG_MEDIA_ERRORS or last_error.startswith("BACKLOG_ARTICLE_IDENTITY_AMBIGUOUS"):
            continue
        recoverable.append(row)
    return sorted(recoverable, key=lambda row: str(row.get("cycle") or ""), reverse=True)


def backlog_may_run(state, *, current_cycle_complete: bool) -> bool:
    """Allow backlog work only when it cannot starve an actionable current cycle.

    The only incomplete-current-cycle exception is the pre-publication waiting
    window, where there is nothing useful to advance yet. Once today's article,
    Overview or Short is actionable/in-flight/blocked, current-cycle ownership
    wins until the strict A+B+C delivery contract is complete.
    """
    if current_cycle_complete:
        return True
    return str((state or {}).get("status") or "") == "waiting_for_article_window"


class RuntimeV5Controller(three_strike.ThreeStrikeMediaInterventionMixin, base_runtime.RuntimeV5Controller):
    """Existing V5 runtime with current-cycle delivery ahead of backlog recovery."""

    PIPELINE_ID = "v5"

    def _dispatch_worker(self, workflow, inputs):
        if hasattr(self.github, "request"):
            v5.core.GitHubClient.dispatch(self.github, workflow, inputs)
            return
        self.github.dispatch(workflow, inputs)

    def _backlog_row_source(self, row, posts, state):
        media = row.setdefault("media", {})
        cycle = str(row.get("cycle") or "").strip()
        if not cycle:
            return None, None
        matches = self._posts_for_date(cycle, posts)
        if not matches:
            return None, None
        row_slug = str((row.get("article") or {}).get("slug") or media.get("source_slug") or "").strip()
        expected_sha = str((row.get("article") or {}).get("quality_content_sha256") or "").strip()
        if row_slug:
            slug_matches = [
                p for p in matches
                if str(p.get("slug") or p.get("id") or "").strip() == row_slug
                and v5.core.is_controller_adoptable_post(
                    p,
                    state_slug=row_slug,
                    state_content_sha256=expected_sha,
                )
            ]
            resolved_matches = slug_matches if len(slug_matches) == 1 else []
        elif cycle in v5.core.REVIEWED_AMBIGUOUS_POST_FREEZE_DATES:
            resolved_matches = []
        else:
            cm_matches = [
                p for p in matches
                if v5.core.is_controller_adoptable_post(p)
            ]
            resolved_matches = cm_matches if len(cm_matches) == 1 else []

        if len(resolved_matches) == 1 and expected_sha:
            candidate_source = v5.article_source_identity(resolved_matches[0])
            if candidate_source["content_sha256"] != expected_sha:
                resolved_matches = []

        if len(resolved_matches) != 1:
            candidate_slugs = [
                str(p.get("slug") or p.get("id") or "").strip()
                for p in matches
                if isinstance(p, dict)
            ]
            media.update({
                "status": "quarantined_ambiguous_identity",
                "long_status": "quarantined_ambiguous_identity",
                "quarantined": True,
                "quarantined_at": v5.core.utc_now(),
                "quarantine_reason": "BACKLOG_ARTICLE_IDENTITY_AMBIGUOUS",
                "last_error": f"BACKLOG_ARTICLE_IDENTITY_AMBIGUOUS: {cycle}",
                "ambiguous_candidate_slugs": candidate_slugs,
                "ambiguous_candidate_count": len(matches),
            })
            row["status"] = "quarantined_ambiguous_identity"
            row["quarantined"] = True
            row["last_error"] = f"BACKLOG_ARTICLE_IDENTITY_AMBIGUOUS: {cycle}"
            state.setdefault("history", []).append({
                "at": v5.core.utc_now(),
                "from": state.get("status"),
                "to": state.get("status"),
                "reason": "backlog_quarantined_ambiguous_identity",
                "details": {
                    "cycle": cycle,
                    "candidate_slugs": candidate_slugs,
                },
            })
            state["history"] = state["history"][-100:]
            return None, None
        post = resolved_matches[0]
        source = v5.article_source_identity(post)
        url = f"{v5.core.SITE_URL}/blog/{source['slug']}"
        media.update({
            "source_slug": source["slug"],
            "source_content_sha256": source["content_sha256"],
            "article_title": str(post.get("title") or ""),
            "article_url": url,
            "article_live": False,
        })
        return row, source

    def _published_backlog_sources(self, state, *, require_public=False):
        if (
            type(self)._published_backlog_source != RuntimeV5Controller._published_backlog_source
            or getattr(self._published_backlog_source, "__code__", None) != RuntimeV5Controller._published_backlog_source.__code__
        ):
            res = self._published_backlog_source(state, require_public=require_public)
            return [res] if res[0] is not None else []
        posts = self.posts_on_main("main")
        backlog_rows = state.get("backlog")
        if not backlog_rows:
            backlog_rows = state.get("media_recovery_backlog") or []
        backlog = ordered_recoverable_backlog(backlog_rows)
        results = []
        for row in backlog:
            row, source = self._backlog_row_source(row, posts, state)
            if row is None or source is None:
                continue
            if require_public:
                url = row["media"]["article_url"]
                status, body = self.site.get(url)
                if status != 200 or not v5.core.article_is_public(
                    body,
                    row["media"]["article_title"],
                    source["slug"],
                    source["content_sha256"],
                ):
                    continue
                row["media"]["article_live"] = True
            results.append((row, source))
        return results

    def _published_backlog_source(self, state, *, require_public=True):
        sources = self._published_backlog_sources(state, require_public=require_public)
        return sources[0] if sources else (None, None)

    @staticmethod
    def _historical_backlog_short_verified(item, source) -> bool:
        if str(source.get("date") or "") >= "2026-10-04":
            return False
        if v5._source_identity(item) != (source["slug"], source["content_sha256"]):
            return False
        if item.get("source_mode") == "overview-segment":
            return False
        if not v5.core.verified_youtube_item(item, source["slug"]):
            return False
        media = item.get("media") or {}
        try:
            width = int(media.get("width") or 0)
            height = int(media.get("height") or 0)
        except (TypeError, ValueError):
            return False
        if width != 1080 or height != 1920 or height <= width:
            return False
        if item.get("signature_verified") is not True or item.get("signature_fullscreen") is not True:
            return False
        try:
            sig_duration = float(item.get("signature_duration_seconds") or 0)
        except (TypeError, ValueError):
            return False
        if abs(sig_duration - 3.0) >= 0.001:
            return False
        return bool(str(item.get("signature_video_sha256") or "").strip())

    def _verified_backlog_short(self, source, long_item=None):
        snapshot = self.github.newest_short_state()
        short_rows = (
            self._exact_short_items(snapshot, source, long_item=long_item)
            if hasattr(self, "_exact_short_items")
            else v5._exact_items(snapshot, source)
        )
        rows = [
            row
            for row in short_rows
            if delivery_guard.short_public_portrait_verified(
                row,
                source,
                youtube_verified=v5.core.verified_youtube_item,
            )
            or self._historical_backlog_short_verified(row, source)
        ]
        return v5._newest(rows)

    def _backlog_media_preflight(self, state):
        candidates = self._published_backlog_sources(state, require_public=False)
        if not candidates:
            return None

        has_unresolved_exhausted = False

        for row, source in candidates:
            media = row["media"]
            article_url = str(media.get("article_url") or f"{v5.core.SITE_URL}/blog/{source['slug']}")
            status, body = self.site.get(article_url)
            article_live = status == 200 and v5.core.article_is_public(
                body,
                str(media.get("article_title") or ""),
                source["slug"],
                source["content_sha256"],
            )
            media["article_live"] = bool(article_live)

            if not article_live:
                if self.github.active_workflow_run(v5.core.DEPLOY_WORKFLOW, production_only=True):
                    media["article_deploy_status"] = "running"
                    return v5.core.Action("wait", "prior-cycle article deployment is already active")

                article_state = row.setdefault("article", {})
                deploy_count = int(article_state.get("deploy_attempts") or 0)
                if deploy_count >= MAX_BACKLOG_DEPLOY_DISPATCHES:
                    media["article_deploy_status"] = "exhausted"
                    media["last_error"] = "BACKLOG_ARTICLE_DEPLOY_ATTEMPTS_EXHAUSTED"
                    has_unresolved_exhausted = True
                    continue

                self.github.dispatch(v5.core.DEPLOY_WORKFLOW)
                article_state.update({
                    "deploy_attempts": deploy_count + 1,
                    "last_deploy_dispatch_at": v5.core.utc_now(),
                })
                media.update({
                    "article_deploy_status": "running",
                    "article_last_deploy_dispatch_at": v5.core.utc_now(),
                    "last_error": None,
                })
                return v5.core.Action(
                    "dispatch_backlog_deploy",
                    "dispatched deployment for exact prior-cycle article already present on main",
                    {
                        "target_slug": source["slug"],
                        "target_content_sha256": source["content_sha256"],
                    },
                )

            media["article_deploy_status"] = "complete"
            if media.get("last_error") == "BACKLOG_ARTICLE_DEPLOY_ATTEMPTS_EXHAUSTED":
                media["last_error"] = None

            long_state = self.github.newest_video_state()
            long_verified = v5._newest(v5._verified_exact(long_state, source))
            short_verified = (
                self._verified_backlog_short(source, long_item=long_verified)
                if long_verified is not None
                else None
            )

            if long_verified is not None:
                media.update({
                    "long_status": "complete",
                    "long_item_id": long_verified.get("id"),
                    "long_youtube_url": long_verified.get("youtube_url"),
                    "long_youtube_id": long_verified.get("youtube_id"),
                })
                if short_verified is not None:
                    short_media = short_verified.get("media") or {}
                    media.update({
                        "short_status": "complete",
                        "short_item_id": short_verified.get("id"),
                        "short_youtube_url": short_verified.get("youtube_url"),
                        "short_youtube_id": short_verified.get("youtube_id"),
                        "short_width": short_media.get("width"),
                        "short_height": short_media.get("height"),
                        "complete": True,
                        "completed_at": v5.core.utc_now(),
                    })
                    v5.core.transition(
                        state,
                        state.get("status") or "article_generating",
                        "prior-cycle article media delivery verified without disturbing current cycle",
                        backlog_cycle=row.get("cycle"),
                        source_slug=source["slug"],
                    )
                    continue

                active_short = self.github.active_workflow_run(v5.SHORT_WORKFLOW, production_only=True)
                if active_short:
                    media["short_status"] = "running"
                    return v5.core.Action("wait", "prior-cycle exact Short workflow is already active")

                signature = self._signature_asset_path()
                if not signature.is_file() or signature.stat().st_size <= 0:
                    media["short_status"] = "blocked"
                    media["last_error"] = "SHORT_SIGNATURE_ASSET_MISSING"
                    return v5.core.Action("blocked", "prior-cycle Short signature asset is missing")

                gate_error = self._short_dispatch_gate_error(source, long_verified)
                if gate_error is not None:
                    code, message = gate_error
                    media["short_status"] = "blocked"
                    media["last_error"] = code
                    return v5.core.Action("blocked", message)

                count = int(media.get("short_dispatch_count") or 0)
                if count >= MAX_BACKLOG_SHORT_DISPATCHES:
                    media["short_status"] = "exhausted"
                    media["last_error"] = "BACKLOG_SHORT_ATTEMPTS_EXHAUSTED"
                    has_unresolved_exhausted = True
                    continue

                inputs = {
                    "operation": "derive",
                    "derive_slug": source["slug"],
                    "derive_content_sha256": source["content_sha256"],
                    "derive_long_item_id": str(long_verified.get("id") or ""),
                }
                self._dispatch_worker(v5.SHORT_WORKFLOW, inputs)
                media.update({
                    "short_status": "running",
                    "short_dispatch_count": count + 1,
                    "short_last_dispatch_at": v5.core.utc_now(),
                })
                v5.core.transition(
                    state,
                    state.get("status") or "article_generating",
                    "dispatched independent prior-cycle Short generation",
                    backlog_cycle=row.get("cycle"),
                    source_slug=source["slug"],
                )
                return v5.core.Action("dispatch_backlog_short", "dispatched independent prior-cycle Short", inputs)

            active_long = self.github.active_workflow_run(v5.LONG_VIDEO_WORKFLOW, production_only=True)
            active_seed = self.github.active_workflow_run(BACKLOG_MEDIA_RECOVERY_WORKFLOW, production_only=True)
            if active_long or active_seed:
                media["long_status"] = "running"
                return v5.core.Action("wait", "prior-cycle exact long-video recovery is already active")

            exact_unresolved = [
                item
                for item in v5._exact_items(long_state, source)
                if item.get("uploaded") is not True
                and str(item.get("status") or "") in (v5.core.ACTIVE_VIDEO_STATUSES | {"rejected"})
            ]
            if len(exact_unresolved) > 1:
                media["long_status"] = "blocked"
                media["last_error"] = "DUPLICATE_BACKLOG_LONG_ITEMS"
                return v5.core.Action("blocked", "duplicate prior-cycle long-video items")

            if exact_unresolved:
                exact_item = exact_unresolved[0]
                if legacy_immutable_evidence_gap(exact_item):
                    rebuild_count = int(media.get("long_evidence_rebuild_count") or 0)
                    if rebuild_count >= MAX_BACKLOG_EVIDENCE_REBUILDS:
                        media["long_status"] = "exhausted"
                        media["last_error"] = "BACKLOG_LEGACY_EVIDENCE_REBUILD_EXHAUSTED"
                        has_unresolved_exhausted = True
                        continue

                    inputs = {
                        "operation": "rebuild",
                        "rebuild_item_id": str(exact_item.get("id") or ""),
                        "target_slug": source["slug"],
                        "target_content_sha256": source["content_sha256"],
                        "target_item_id": str(exact_item.get("id") or ""),
                    }
                    self._dispatch_worker(v5.LONG_VIDEO_WORKFLOW, inputs)
                    media.update({
                        "long_status": "running",
                        "long_evidence_rebuild_count": rebuild_count + 1,
                        "long_last_dispatch_at": v5.core.utc_now(),
                        "last_error": None,
                    })
                    return v5.core.Action(
                        "dispatch_backlog_long_rebuild",
                        "rebuilding exact prior-cycle legacy evidence without new provider generation",
                        inputs,
                    )

                inputs = {
                    "operation": "full",
                    "target_slug": source["slug"],
                    "target_content_sha256": source["content_sha256"],
                    "target_item_id": str(exact_item.get("id") or ""),
                }
                if not inputs["target_item_id"]:
                    raise v5.core.ControllerError("LONG_VIDEO_ITEM_ID_MISSING")
                self._dispatch_worker(v5.LONG_VIDEO_WORKFLOW, inputs)
                media.update({
                    "long_status": "running",
                    "long_resume_count": int(media.get("long_resume_count") or 0) + 1,
                    "long_last_dispatch_at": v5.core.utc_now(),
                })
                return v5.core.Action("dispatch_backlog_long_video", "resumed exact prior-cycle long-video identity", inputs)

            count = int(media.get("seed_dispatch_count") or 0)
            if count >= MAX_BACKLOG_SEED_DISPATCHES:
                media["long_status"] = "exhausted"
                media["last_error"] = "BACKLOG_EXACT_SEED_ATTEMPTS_EXHAUSTED"
                has_unresolved_exhausted = True
                continue

            inputs = {
                "operation": "full",
                "target_slug": source["slug"],
                "target_content_sha256": source["content_sha256"],
            }
            self._dispatch_worker(v5.LONG_VIDEO_WORKFLOW, inputs)
            media.update({
                "long_status": "running",
                "seed_dispatch_count": count + 1,
                "long_last_dispatch_at": v5.core.utc_now(),
            })
            v5.core.transition(
                state,
                state.get("status") or "article_generating",
                "dispatched exact prior-cycle long-video state handoff before current-cycle watchdog",
                backlog_cycle=row.get("cycle"),
                source_slug=source["slug"],
            )
            return v5.core.Action("dispatch_backlog_long_video", "seeded exact prior-cycle long-video recovery", inputs)

        if has_unresolved_exhausted:
            return v5.core.Action(
                "backlog_unresolved",
                "prior-cycle backlog items remain unresolved or exhausted",
            )
        return None

    def tick(self):
        # Always reconcile/advance today's authoritative identity first. This is
        # the guard against backlog starvation: a historical row may never make
        # us skip the current-cycle watchdog, recovery or direct-takeover logic.
        state, current_action = super().tick()
        current_cycle_complete, deliverables = delivery_guard.delivery_contract(state)
        state["deliverables"] = deliverables

        if not backlog_may_run(state, current_cycle_complete=current_cycle_complete):
            self.github.save_controller_state(state)
            return state, current_action

        backlog_action = self._backlog_media_preflight(state)
        self.github.save_controller_state(state)
        if backlog_action is not None and backlog_action.kind != "backlog_unresolved":
            _, deliverables = delivery_guard.delivery_contract(state)
            state["deliverables"] = deliverables
            self.github.save_controller_state(state)
            return state, backlog_action
        return state, current_action


def install_runtime() -> None:
    base_runtime.install_runtime()
    v5.V5Controller = RuntimeV5Controller


def main() -> int:
    from scripts.kesher_runtime.legacy_retirement import retired_entrypoint
    retired_entrypoint()
    install_runtime()
    return v5.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (v5.core.ControllerError, ValueError, KeyError) as exc:
        print(f"KESHER_CONTROLLER_V5_RUNTIME_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)
