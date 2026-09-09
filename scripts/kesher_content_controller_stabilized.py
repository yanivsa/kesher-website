#!/usr/bin/env python3
"""Production Kesher V5 runtime with fail-closed article and media-quality preflights."""

from __future__ import annotations

import json
import sys

if __package__:
    from . import article_claim_quality as quality
    from . import kesher_content_controller_v5 as v5
    from . import kesher_content_controller_v5_runtime as runtime
else:
    import article_claim_quality as quality
    import kesher_content_controller_v5 as v5
    import kesher_content_controller_v5_runtime as runtime


class StabilizedRuntimeV5Controller(runtime.RuntimeV5Controller):
    """Prevent advancement/completion unless article and canonical media evidence are durable."""

    def _quality_preflight(self, state):
        posts = self.github.contents_json("src/data/posts.json", "main")
        if not isinstance(posts, list):
            raise v5.core.ControllerError("ARTICLE_SOURCE_INVALID")
        todays = v5.core.today_articles(posts, self.now.date())
        if len(todays) != 1:
            return None

        article = todays[0]
        source = v5.article_source_identity(article)
        violations = quality.article_violations(article)
        state["article"].update({
            "quality_status": "failed" if violations else "passed",
            "quality_content_sha256": source["content_sha256"],
            "quality_checked_at": v5.core.utc_now(),
            "quality_violations": violations,
        })
        if not violations:
            return None

        message = " | ".join(violations[:3])
        v5.core.block(
            state,
            "article",
            quality.ERROR_CODE,
            f"article quality gate failed for {source['slug']}@{source['content_sha256'][:12]}: {message}",
        )
        self.github.save_controller_state(state)
        return v5.core.Action("blocked", "article content quality failed before deploy/media")

    def _overview_evidence_preflight(self, state):
        """Copy exact public Overview edit evidence into durable controller state."""
        source = self._article_source()
        if source is None:
            return

        # Production is fail-closed: once an authoritative article exists, a
        # public URL alone is never sufficient to complete the Overview stage.
        state["long_video"]["overview_evidence_required"] = True

        snapshot = self.github.newest_video_state()
        item = v5._newest(v5._verified_exact(snapshot, source))
        if item is None:
            item = self._verified_long_from_artifact_history(source)
        if item is None:
            return

        media = item.get("media") or {}
        state["long_video"].update({
            "item_id": item.get("id"),
            "youtube_id": item.get("youtube_id"),
            "youtube_url": item.get("youtube_url"),
            "verified": True,
            "technical_verified": item.get("technical_verified") is True,
            "visual_pipeline": item.get("visual_pipeline"),
            "codec": media.get("codec"),
            "width": media.get("width"),
            "height": media.get("height"),
            "duration": media.get("duration"),
            "content_duration_seconds": item.get("content_duration_seconds"),
            "signature_duration_seconds": item.get("signature_duration_seconds"),
            "signature_fullscreen": item.get("signature_fullscreen"),
            "signature_asset_sha256": item.get("signature_asset_sha256"),
            "provider_id": item.get("task_id"),
            "artifact_id": item.get("artifact_id"),
            "source_id": item.get("source_id"),
        })

    def tick(self):
        state = self.state()
        blocker = self._quality_preflight(state)
        if blocker is not None:
            return state, blocker

        self._overview_evidence_preflight(state)
        self.github.save_controller_state(state)
        return super().tick()


def install_runtime() -> None:
    runtime.install_runtime()
    v5.V5Controller = StabilizedRuntimeV5Controller


def main() -> int:
    install_runtime()
    return v5.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (v5.core.ControllerError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"KESHER_CONTROLLER_STABILIZED_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)