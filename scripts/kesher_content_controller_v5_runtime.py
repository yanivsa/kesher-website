#!/usr/bin/env python3
"""Production runtime activation plus exact prior-cycle media recovery."""

from __future__ import annotations

import copy
import sys

if __package__:
    from . import kesher_content_controller_v5 as v5
    from . import kesher_content_controller_v5_runtime_base as base_runtime
    from . import kesher_e2e_delivery_guard as delivery_guard
else:
    import kesher_content_controller_v5 as v5
    import kesher_content_controller_v5_runtime_base as base_runtime
    import kesher_e2e_delivery_guard as delivery_guard

ARTICLE_AUTO_MERGE_WORKFLOW = base_runtime.ARTICLE_AUTO_MERGE_WORKFLOW
MEDIA_WATCHDOG_STATUSES = base_runtime.MEDIA_WATCHDOG_STATUSES
DEFAULT_SIGNATURE_ASSET = "public/images/signature/signature-mask.svg"
BACKLOG_MEDIA_RECOVERY_WORKFLOW = "kesher-backlog-media-recovery.yml"
MAX_BACKLOG_SEED_DISPATCHES = 3
MAX_BACKLOG_SHORT_DISPATCHES = 4


class RuntimeV5Controller(base_runtime.RuntimeV5Controller):
    """Existing V5 runtime with prior-cycle delivery reconciliation first."""

    def _published_backlog_source(self, state):
        posts = self.github.contents_json("src/data/posts.json", "main")
        if not isinstance(posts, list):
            raise v5.core.ControllerError("ARTICLE_SOURCE_INVALID")

        backlog = sorted(
            [row for row in (state.get("backlog") or []) if isinstance(row, dict)],
            key=lambda row: str(row.get("cycle") or ""),
        )
        for row in backlog:
            media = row.setdefault("media", {})
            if media.get("complete") is True:
                continue
            cycle = str(row.get("cycle") or "").strip()
            if not cycle:
                continue
            matches = [post for post in posts if isinstance(post, dict) and str(post.get("date") or "") == cycle]
            if not matches:
                continue
            if len(matches) != 1:
                raise v5.core.ControllerError(f"BACKLOG_ARTICLE_IDENTITY_AMBIGUOUS: {cycle}")
            post = matches[0]
            source = v5.article_source_identity(post)
            url = f"{v5.core.SITE_URL}/blog/{source['slug']}"
            status, body = self.site.get(url)
            if status != 200 or not v5.core.article_is_public(body, str(post.get("title") or "")):
                continue
            media.update({
                "source_slug": source["slug"],
                "source_content_sha256": source["content_sha256"],
                "article_url": url,
                "article_live": True,
            })
            return row, source
        return None, None

    def _verified_backlog_short(self, source):
        snapshot = self.github.newest_short_state()
        rows = [
            row
            for row in v5._exact_items(snapshot, source)
            if delivery_guard.short_public_portrait_verified(
                row,
                source,
                youtube_verified=v5.core.verified_youtube_item,
            )
        ]
        return v5._newest(rows)

    def _backlog_media_preflight(self, state):
        row, source = self._published_backlog_source(state)
        if row is None or source is None:
            return None
        media = row["media"]

        long_state = self.github.newest_video_state()
        long_verified = v5._newest(v5._verified_exact(long_state, source))
        short_verified = self._verified_backlog_short(source) if long_verified is not None else None

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
                return None

            active_short = self.github.active_workflow_run(v5.SHORT_WORKFLOW, production_only=True)
            if active_short:
                media["short_status"] = "running"
                return v5.core.Action("wait", "prior-cycle exact Short workflow is already active")

            signature = self._signature_asset_path()
            if not signature.is_file() or signature.stat().st_size <= 0:
                media["short_status"] = "blocked"
                media["last_error"] = "SHORT_SIGNATURE_ASSET_MISSING"
                return v5.core.Action("blocked", "prior-cycle Short signature asset is missing")

            count = int(media.get("short_dispatch_count") or 0)
            if count >= MAX_BACKLOG_SHORT_DISPATCHES:
                media["short_status"] = "exhausted"
                media["last_error"] = "BACKLOG_SHORT_ATTEMPTS_EXHAUSTED"
                return v5.core.Action("blocked", "prior-cycle Short recovery attempts exhausted")

            inputs = {
                "operation": "derive",
                "derive_slug": source["slug"],
                "derive_content_sha256": source["content_sha256"],
                "derive_long_item_id": str(long_verified.get("id") or ""),
            }
            v5.core.GitHubClient.dispatch(self.github, v5.SHORT_WORKFLOW, inputs)
            media.update({
                "short_status": "running",
                "short_dispatch_count": count + 1,
                "short_last_dispatch_at": v5.core.utc_now(),
                "long_provider_id": long_verified.get("task_id"),
                "long_artifact_id": long_verified.get("artifact_id"),
            })
            v5.core.transition(
                state,
                state.get("status") or "article_generating",
                "dispatched exact prior-cycle Short from verified long-form identity",
                backlog_cycle=row.get("cycle"),
                source_slug=source["slug"],
                long_item_id=long_verified.get("id"),
            )
            return v5.core.Action("dispatch_backlog_short", "dispatched exact prior-cycle Short", inputs)

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
            inputs = {"operation": "full"}
            v5.core.GitHubClient.dispatch(self.github, v5.LONG_VIDEO_WORKFLOW, inputs)
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
            return v5.core.Action("blocked", "prior-cycle exact long-video seed attempts exhausted")

        inputs = {
            "target_slug": source["slug"],
            "target_content_sha256": source["content_sha256"],
        }
        v5.core.GitHubClient.dispatch(self.github, BACKLOG_MEDIA_RECOVERY_WORKFLOW, inputs)
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

    def tick(self):
        state = self.state()
        backlog_action = self._backlog_media_preflight(state)
        self.github.save_controller_state(state)
        if backlog_action is not None:
            _, deliverables = delivery_guard.delivery_contract(state)
            state["deliverables"] = deliverables
            self.github.save_controller_state(state)
            return state, backlog_action
        return super().tick()


def install_runtime() -> None:
    base_runtime.install_runtime()
    v5.V5Controller = RuntimeV5Controller


def main() -> int:
    install_runtime()
    return v5.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (v5.core.ControllerError, ValueError, KeyError) as exc:
        print(f"KESHER_CONTROLLER_V5_RUNTIME_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)
