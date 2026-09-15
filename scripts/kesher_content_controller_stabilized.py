#!/usr/bin/env python3
"""Production Kesher V5 runtime with fail-closed article and media-quality preflights."""

from __future__ import annotations

import json
import sys
import urllib.parse

if __package__:
    from . import article_claim_quality as quality
    from . import kesher_content_controller_v5 as v5
    from . import kesher_content_controller_v5_runtime as runtime
else:
    import article_claim_quality as quality
    import kesher_content_controller_v5 as v5
    import kesher_content_controller_v5_runtime as runtime


_ORIGINAL_PUBLIC_SITE_GET = v5.core.PublicSiteClient.get


def _unicode_safe_public_site_get(self, url: str):
    """Percent-encode non-ASCII URL components before urllib builds the request."""
    parts = urllib.parse.urlsplit(url)
    safe_url = urllib.parse.urlunsplit((
        parts.scheme,
        parts.netloc,
        urllib.parse.quote(parts.path, safe="/%:@"),
        urllib.parse.quote(parts.query, safe="=&%:@/?+"),
        urllib.parse.quote(parts.fragment, safe="%:@/?+"),
    ))
    return _ORIGINAL_PUBLIC_SITE_GET(self, safe_url)


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

    def _dispatch_budgeted(self, state, stage, workflow, inputs):
        """Bind long-video dispatch and provider resume to the authoritative source identity."""
        bound_inputs = dict(inputs or {})
        if stage != "video" or workflow != v5.LONG_VIDEO_WORKFLOW:
            return super()._dispatch_budgeted(state, stage, workflow, bound_inputs)

        source = self._article_source()
        if source is None:
            raise v5.core.ControllerError("LONG_VIDEO_SOURCE_IDENTITY_UNAVAILABLE")
        target_slug = str(bound_inputs.get("target_slug") or "").strip()
        if bound_inputs.get("operation") in {"full", "generate"}:
            if target_slug and target_slug != source["slug"]:
                raise v5.core.ControllerError("LONG_VIDEO_SOURCE_IDENTITY_MISMATCH")
            bound_inputs["target_slug"] = source["slug"]

        snapshot = self.github.newest_video_state()
        exact_generating = [
            item for item in v5._exact_items(snapshot, source)
            if item.get("uploaded") is not True
            and str(item.get("status") or "") == "generating"
            and str(item.get("source_id") or "").strip()
            and str(item.get("task_id") or "").strip()
            and str(item.get("artifact_id") or "").strip()
            and str(item.get("task_id") or "").strip() == str(item.get("artifact_id") or "").strip()
        ]
        if len(exact_generating) > 1:
            raise v5.core.ControllerError("DUPLICATE_LONG_VIDEO_PROVIDER_TASKS")
        if exact_generating:
            item = exact_generating[0]
            v5.core.GitHubClient.dispatch(self.github, workflow, bound_inputs)
            current = state["video"]
            current["attempt_count"] = max(1, int(current.get("attempt_count") or 0))
            current["resume_dispatches"] = int(current.get("resume_dispatches") or 0) + 1
            current["last_dispatch_at"] = v5.core.utc_now()
            current["status"] = "running"
            current["next_retry_at"] = None
            current["item_id"] = item.get("id")
            current["source_id"] = item.get("source_id")
            current["artifact_id"] = item.get("artifact_id")
            current["provider_id"] = item.get("task_id")
            return

        # No exact provider task is currently generating. Use the bounded V3
        # dispatch budget rather than the legacy global FIFO provider-resume
        # lookup, which can bind a different article's provider identity.
        return v5.v3.V3Controller._dispatch_budgeted(self, state, stage, workflow, bound_inputs)

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
    v5.core.PublicSiteClient.get = _unicode_safe_public_site_get
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
