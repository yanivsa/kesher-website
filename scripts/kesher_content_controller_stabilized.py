#!/usr/bin/env python3
"""Production Kesher V5 runtime with a fail-closed article quality preflight."""

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
    """Prevent deploy/media advancement from an article that fails quality policy."""

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

    def tick(self):
        state = self.state()
        blocker = self._quality_preflight(state)
        if blocker is not None:
            return state, blocker
        # Persist the pass bound to the exact authoritative content hash before
        # V5 may dispatch a deploy, Overview or Short. super().tick() reloads
        # this durable state through the same controller state ref.
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
