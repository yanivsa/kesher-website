#!/usr/bin/env python3
"""Production runtime activation for Kesher V5 shared-provider publishing."""

from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

if __package__:
    from . import kesher_content_controller_v5 as v5
    from . import kesher_content_watchdog as watchdog
    from . import kesher_e2e_delivery_guard as delivery_guard
else:
    import kesher_content_controller_v5 as v5
    import kesher_content_watchdog as watchdog
    import kesher_e2e_delivery_guard as delivery_guard

ARTICLE_AUTO_MERGE_WORKFLOW = "auto-merge-article-prs.yml"
MEDIA_WATCHDOG_STATUSES = {"source_selected", "source_added", "generating"}
DEFAULT_SIGNATURE_ASSET = "public/shira-signature.mp4"


class RuntimeV5Controller(v5.V5Controller):
    """V5 plus bounded media recovery and a strict three-link delivery contract."""

    def _signature_asset_path(self) -> Path:
        configured = os.environ.get("KESHER_SHORT_SIGNATURE_VIDEO", "").strip()
        return Path(configured or DEFAULT_SIGNATURE_ASSET)

    def _signature_asset_blocker(self, state):
        """Fail closed before Short dispatch when the approved signature clip is absent."""
        path = self._signature_asset_path()
        if path.is_file() and path.stat().st_size > 0:
            return None
        v5.core.block(
            state,
            "short",
            "SHORT_SIGNATURE_ASSET_MISSING",
            f"approved Shira signature video asset/path is missing: {path}",
        )
        state["short"]["status"] = "blocked"
        return v5.core.Action("blocked", "approved Shira signature video asset/path is missing")

    def _tick_short(self, state, source, long_item):
        blocker = self._signature_asset_blocker(state)
        if blocker is not None:
            return blocker
        return super()._tick_short(state, source, long_item)

    def _adopt_existing_short(self, state, source):
        short_state = self.github.newest_short_state()
        verified = [
            row
            for row in v5._exact_items(short_state, source)
            if delivery_guard.short_public_portrait_verified(
                row,
                source,
                youtube_verified=v5.core.verified_youtube_item,
            )
        ]
        item = v5._newest(verified)
        if not item:
            return None
        media = item.get("media") or {}
        state["short"].update({
            "item_id": item.get("id"),
            "status": "complete",
            "youtube_id": item.get("youtube_id"),
            "youtube_url": item.get("youtube_url"),
            "verified": True,
            "portrait_verified": True,
            "signature_verified": item.get("signature_verified") is True,
            "signature_duration_seconds": item.get("signature_duration_seconds"),
            "signature_fullscreen": item.get("signature_fullscreen") is True,
            "signature_video_sha256": item.get("signature_video_sha256"),
            "width": media.get("width"),
            "height": media.get("height"),
            "provider_id": item.get("task_id"),
            "artifact_id": item.get("artifact_id"),
            "source_id": item.get("source_id"),
        })
        v5.v3.clear_stage_failure(state["short"])
        return item

    @staticmethod
    def _watchdog_candidate(snapshot, source):
        rows = [
            row
            for row in v5._exact_items(snapshot, source)
            if str(row.get("status") or "") in MEDIA_WATCHDOG_STATUSES
            and row.get("uploaded") is not True
        ]
        return v5._newest(rows)

    def _verified_long_from_artifact_history(self, source):
        """Recover exact public long-form evidence that a newer state artifact lost.

        The normal fast path still reads only the newest state artifact. This
        bounded fallback is used only when that newest state has no exact public
        Overview for the authoritative slug + content hash.
        """
        injected = getattr(self.github, "verified_video_item_from_history", None)
        if callable(injected):
            item = injected(source)
            if (
                isinstance(item, dict)
                and v5._source_identity(item) == (source["slug"], source["content_sha256"])
                and v5.core.verified_youtube_item(item, source["slug"])
            ):
                return item
            return None

        payload = self.github.request(
            "GET",
            f"{self.github.api}/actions/artifacts?name={v5.LONG_VIDEO_STATE_ARTIFACT}&per_page=30",
        )
        artifacts = [
            row
            for row in ((payload or {}).get("artifacts") or [])
            if isinstance(row, dict)
            and not row.get("expired")
            and row.get("archive_download_url")
        ]
        artifacts.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)

        for artifact in artifacts:
            try:
                raw = self.github.download_artifact_archive(str(artifact["archive_download_url"]))
                with v5.core.zipfile.ZipFile(v5.core.io.BytesIO(raw)) as archive:
                    names = [name for name in archive.namelist() if name.endswith("state.json")]
                    if not names:
                        continue
                    snapshot = v5.json.loads(archive.read(names[0]).decode("utf-8"))
            except (
                v5.core.ControllerError,
                v5.core.zipfile.BadZipFile,
                v5.json.JSONDecodeError,
                UnicodeDecodeError,
                KeyError,
            ):
                continue
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get("items"), list):
                continue
            item = v5._newest(v5._verified_exact(snapshot, source))
            if item is not None:
                return item
        return None

    def _reconcile_historical_long_and_advance_short(self, state, source):
        """Adopt a lost-but-public Overview and advance its Short in this tick."""
        newest = self.github.newest_video_state()
        if v5._newest(v5._verified_exact(newest, source)) is not None:
            return None

        long_item = self._verified_long_from_artifact_history(source)
        if long_item is None:
            return None

        state["long_video"].update({
            "item_id": long_item.get("id"),
            "status": "complete",
            "youtube_id": long_item.get("youtube_id"),
            "youtube_url": long_item.get("youtube_url"),
            "verified": True,
            "provider_id": long_item.get("task_id"),
            "artifact_id": long_item.get("artifact_id"),
            "source_id": long_item.get("source_id"),
        })
        v5.v3.clear_stage_failure(state["long_video"])
        v5.core.transition(
            state,
            "long_video_complete",
            "reconciled exact verified public Overview from historical durable state",
            item_id=long_item.get("id"),
            youtube_url=long_item.get("youtube_url"),
        )
        return self._tick_short(state, source, long_item)

    def _recover_long_video(self, state, source, item):
        inputs = {"operation": "full"}
        v5.core.GitHubClient.dispatch(self.github, v5.LONG_VIDEO_WORKFLOW, inputs)
        watchdog.mark_media_recovery(state["long_video"], now=self.now)
        state["long_video"]["status"] = "running"
        state["long_video"]["last_dispatch_at"] = v5.core.utc_now()
        state["long_video"]["resume_dispatches"] = int(
            state["long_video"].get("resume_dispatches") or 0
        ) + 1
        v5.core.transition(
            state,
            "long_video_watchdog_recovery",
            "long-form provider stalled; resumed the same durable provider identity",
            item_id=item.get("id"),
            task_id=item.get("task_id"),
        )
        return v5.core.Action("long_video_watchdog_recover", "resumed same long-form provider identity", inputs)

    def _recover_short(self, state, source, item, long_item):
        blocker = self._signature_asset_blocker(state)
        if blocker is not None:
            return blocker
        count = int(state["short"].get("attempt_count") or 0)
        if count >= v5.MAX_SHORT_DISPATCH_ATTEMPTS:
            v5.core.block(
                state,
                "short",
                "SHORT_ATTEMPTS_EXHAUSTED",
                f"Short exhausted {v5.MAX_SHORT_DISPATCH_ATTEMPTS} derive/recovery dispatch attempts",
            )
            state["short"]["status"] = "exhausted"
            return v5.core.Action("blocked", "Short attempts exhausted")
        inputs = {
            "operation": "derive",
            "derive_slug": source["slug"],
            "derive_content_sha256": source["content_sha256"],
            "derive_long_item_id": str(long_item.get("id") or ""),
        }
        v5.core.GitHubClient.dispatch(self.github, v5.SHORT_WORKFLOW, inputs)
        watchdog.mark_media_recovery(state["short"], now=self.now)
        state["short"].update({
            "attempt_count": count + 1,
            "status": "running",
            "last_dispatch_at": v5.core.utc_now(),
            "provider_id": long_item.get("task_id"),
            "artifact_id": long_item.get("artifact_id"),
            "source_id": long_item.get("source_id"),
            "adopted_from_long_item_id": long_item.get("id"),
        })
        v5.core.transition(
            state,
            "short_watchdog_recovery",
            "Short provider stalled; re-dispatched derivation from the same verified long-form identity",
            item_id=item.get("id"),
            long_item_id=long_item.get("id"),
        )
        return v5.core.Action("short_watchdog_recover", "recovered same Short derivation identity", inputs)

    def _media_watchdog_preflight(self, state, source):
        long_state = self.github.newest_video_state()
        long_verified = v5._newest(v5._verified_exact(long_state, source))
        long_candidate = None if long_verified else self._watchdog_candidate(long_state, source)

        stages = []
        if long_candidate is not None:
            stages.append(("long_video", v5.LONG_VIDEO_WORKFLOW, long_candidate, None))
        elif long_verified is not None:
            short_state = self.github.newest_short_state()
            valid_short = [
                row
                for row in v5._exact_items(short_state, source)
                if delivery_guard.short_public_portrait_verified(
                    row,
                    source,
                    youtube_verified=v5.core.verified_youtube_item,
                )
            ]
            if not valid_short:
                short_candidate = self._watchdog_candidate(short_state, source)
                if short_candidate is not None:
                    stages.append(("short", v5.SHORT_WORKFLOW, short_candidate, long_verified))

        for stage_name, workflow, item, long_item in stages:
            stage = state[stage_name]
            identity = f"{stage_name}:{source['slug']}:{item.get('id') or item.get('task_id') or 'unknown'}"
            watchdog.observe_media(
                stage,
                identity=identity,
                fingerprint=delivery_guard.media_fingerprint(item),
                now=self.now,
            )
            active = self.github.active_workflow_run(workflow, production_only=True)
            if active:
                self.github.save_controller_state(state)
                return None

            decision = watchdog.media_decision(stage, now=self.now)
            if decision == "blocked":
                code = "LONG_VIDEO_WATCHDOG_RECOVERY_EXHAUSTED" if stage_name == "long_video" else "SHORT_WATCHDOG_RECOVERY_EXHAUSTED"
                v5.core.block(
                    state,
                    stage_name,
                    code,
                    f"{stage_name} made no durable progress after {watchdog.MAX_MEDIA_RECOVERIES} same-identity recoveries",
                )
                stage["status"] = "exhausted"
                self.github.save_controller_state(state)
                return v5.core.Action("blocked", f"{stage_name} watchdog recovery exhausted")

            if decision == "recover":
                action = (
                    self._recover_long_video(state, source, item)
                    if stage_name == "long_video"
                    else self._recover_short(state, source, item, long_item)
                )
                self.github.save_controller_state(state)
                return action

            v5.core.transition(
                state,
                f"{stage_name}_watchdog_wait",
                f"{stage_name} provider is pending; watchdog is waiting for durable progress before same-identity recovery",
                item_id=item.get("id"),
            )
            self.github.save_controller_state(state)
            return v5.core.Action("wait", f"{stage_name} provider pending under watchdog")
        return None

    def tick(self):
        state = self.state()
        source = self._article_source()
        if source is not None:
            historical_action = self._reconcile_historical_long_and_advance_short(state, source)
            if historical_action is not None:
                _, deliverables = delivery_guard.delivery_contract(state)
                state["deliverables"] = deliverables
                self.github.save_controller_state(state)
                return state, historical_action

            watchdog_action = self._media_watchdog_preflight(state, source)
            if watchdog_action is not None:
                _, deliverables = delivery_guard.delivery_contract(state)
                state["deliverables"] = deliverables
                self.github.save_controller_state(state)
                return state, watchdog_action

        state, action = super().tick()
        ready, deliverables = delivery_guard.delivery_contract(state)
        state["deliverables"] = deliverables
        if action.kind == "complete":
            if not ready:
                v5.core.block(
                    state,
                    "controller",
                    "DELIVERY_CONTRACT_INCOMPLETE",
                    "cycle cannot complete without live article, public Overview, public portrait Short and verified signature ending",
                )
                action = v5.core.Action("blocked", "delivery contract incomplete")
            else:
                action = v5.core.Action(
                    "complete",
                    "article + public Overview + public portrait Short + signature ending verified",
                    copy.deepcopy(deliverables),
                )
        self.github.save_controller_state(state)
        return state, action


def install_runtime() -> None:
    v5.core.VIDEO_WORKFLOW = v5.LONG_VIDEO_WORKFLOW
    v5.core.VIDEO_STATE_ARTIFACT = v5.LONG_VIDEO_STATE_ARTIFACT
    v5.v3.entry.VIDEO_WORKFLOW_NAME = v5.LONG_VIDEO_WORKFLOW_NAME
    v5.v4.AUTO_MERGE_WORKFLOW = ARTICLE_AUTO_MERGE_WORKFLOW
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
