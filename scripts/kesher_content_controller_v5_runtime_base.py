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
DEFAULT_SIGNATURE_ASSET = "public/images/signature/signature-mask.svg"


class RuntimeV5Controller(v5.V5Controller):
    """V5 plus bounded media recovery and a strict three-link delivery contract."""

    AUTO_MERGE_WORKFLOW = ARTICLE_AUTO_MERGE_WORKFLOW

    def _signature_asset_path(self) -> Path:
        configured = os.environ.get("KESHER_SHORT_SIGNATURE_ASSET", "").strip()
        legacy_configured = os.environ.get("KESHER_SHORT_SIGNATURE_VIDEO", "").strip()
        return Path(configured or legacy_configured or DEFAULT_SIGNATURE_ASSET)

    def _signature_asset_blocker(self, state):
        """Fail closed before Short dispatch when the approved signature asset is absent."""
        path = self._signature_asset_path()
        if path.is_file() and path.stat().st_size > 0:
            return None
        v5.core.block(
            state,
            "short",
            "SHORT_SIGNATURE_ASSET_MISSING",
            f"approved Shira signature asset/path is missing: {path}",
        )
        state["short"]["status"] = "blocked"
        return v5.core.Action("blocked", "approved Shira signature asset/path is missing")

    def _tick_short(self, state, source, long_item):
        blocker = self._signature_asset_blocker(state)
        if blocker is not None:
            return blocker
        return super()._tick_short(state, source, long_item)

    def _authoritative_overview_identity(self, source, long_item=None):
        item = long_item
        if not isinstance(item, dict) and hasattr(self.github, "newest_video_state"):
            long_state = self.github.newest_video_state()
            item = v5._newest(v5._verified_exact(long_state, source))
        if (
            not isinstance(item, dict)
            and hasattr(self, "_verified_long_from_artifact_history")
            and hasattr(self.github, "list_workflow_artifacts")
        ):
            item = self._verified_long_from_artifact_history(source)
        if not isinstance(item, dict):
            return None
        identity = {
            field: item.get(field)
            for field in ("notebook_id", "source_id", "task_id", "artifact_id", "raw_sha256")
        }
        if not all(isinstance(identity.get(field), str) and identity[field].strip() for field in identity):
            return None
        return identity

    def _bind_short_overview_identity(self, item, source, long_item=None):
        if not isinstance(item, dict):
            return item
        bound = copy.deepcopy(item)
        overview_identity = self._authoritative_overview_identity(source, long_item=long_item)
        if overview_identity is not None:
            bound["overview_provider_identity"] = overview_identity
        return bound

    def _exact_short_items(self, short_state, source, long_item=None):
        overview_identity = self._authoritative_overview_identity(source, long_item=long_item)
        rows = []
        for row in v5._exact_items(short_state, source):
            bound = copy.deepcopy(row)
            if overview_identity is not None:
                bound["overview_provider_identity"] = copy.deepcopy(overview_identity)
            rows.append(bound)
        return rows

    def _adopt_existing_short(self, state, source):
        current_short = state.get("short") or {}
        if (
            current_short.get("status") == "complete"
            and current_short.get("verified") is True
            and current_short.get("youtube_id")
            and current_short.get("youtube_url")
        ):
            if current_short.get("overview_provider_identity") is None:
                overview_identity = self._authoritative_overview_identity(source)
                if overview_identity is not None:
                    current_short["overview_provider_identity"] = overview_identity
            return current_short
        short_state = self.github.newest_short_state() if hasattr(self.github, "newest_short_state") else {"version": 1, "items": []}
        verified = [
            row
            for row in self._exact_short_items(short_state, source)
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
        sig_verified = delivery_guard._signature_verified(item)
        # Preserve the strict source/audio/signature proof during historical
        # state projection. Boolean summaries cannot replace these receipts.
        # Missing negative flags clear the previous item's stale flags; nested
        # evidence must not share mutable objects with the adopted artifact.
        for field in (
            "source", "notebook_id", "task_id", "raw_sha256", "final_sha256",
            "provider_raw_media", "media", "provider_video_format", "provider_native_short",
            "provider_native_short_verified", "provider_short_fallback_used", "fresh_generation_attempt",
            "overview_provider_identity", "shared_provider_identity", "adopted_from_long_item_id",
            "short_start_seconds", "short_duration_seconds", "audio_provenance",
            "signature_overlay", "signature_provenance", "signature_asset_sha256",
        ):
            state["short"][field] = copy.deepcopy(item.get(field))
        state["short"].update({
            "item_id": item.get("id"),
            "type": item.get("type"),
            "status": "complete",
            "youtube_id": item.get("youtube_id"),
            "youtube_url": item.get("youtube_url"),
            "verified": True,
            "portrait_verified": True,
            "signature_verified": sig_verified,
            "signature_asset": item.get("signature_asset"),
            "signature_sha256": item.get("signature_sha256"),
            "visual_pipeline": item.get("visual_pipeline"),
            "technical_verified": item.get("technical_verified"),
            "signature_duration_seconds": item.get("signature_duration_seconds"),
            "signature_fullscreen": item.get("signature_fullscreen") is True,
            "signature_video_sha256": item.get("signature_video_sha256"),
            "source_mode": item.get("source_mode"),
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
        """Recover exact public long-form evidence from lightweight state history.

        The controller heartbeat must never download the multi-gigabyte durable
        media archives just to inspect ``state.json``. Historical evidence is
        therefore read only from the lightweight controller-state artifacts;
        full durable media remains worker-side recovery material.
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

        if not hasattr(self.github, "request"):
            return None

        payload = self.github.request(
            "GET",
            f"{self.github.api}/actions/artifacts?name={v5.LONG_VIDEO_CONTROLLER_STATE_ARTIFACT}&per_page=30",
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
        newest = self.github.newest_video_state() if hasattr(self.github, "newest_video_state") else {"version": 1, "items": []}
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
        inputs = {
            "operation": "full",
            "target_slug": source["slug"],
            "target_content_sha256": source["content_sha256"],
            "target_item_id": str(item.get("id") or ""),
        }
        v5.core.GitHubClient.dispatch(self.github, v5.LONG_VIDEO_WORKFLOW, inputs)
        watchdog.mark_media_recovery(state["long_video"], now=self.now)
        state["long_video"].update({
            "item_id": item.get("id"),
            "source_slug": source["slug"],
            "source_content_sha256": source["content_sha256"],
            "content_sha256": source["content_sha256"],
            "source_id": item.get("source_id"),
            "task_id": item.get("task_id"),
            "provider_id": item.get("task_id"),
            "artifact_id": item.get("artifact_id"),
            "provider_status": item.get("last_provider_status") or item.get("status"),
            "verified": False,
            "pending_resume_ready": False,
            "status": "running",
            "last_dispatch_at": v5.core.utc_now(),
            "resume_dispatches": int(
                state["long_video"].get("resume_dispatches") or 0
            ) + 1,
        })
        v5.core.transition(
            state,
            "long_video_watchdog_recovery",
            "long-form provider stalled; resumed the same durable provider identity",
            item_id=item.get("id"),
            task_id=item.get("task_id"),
            slug=source["slug"],
            content_sha256=source["content_sha256"],
        )
        return v5.core.Action("long_video_watchdog_recover", "resumed same long-form provider identity", inputs)

    def _recover_short(self, state, source, item, long_item):
        gate_error = self._short_dispatch_gate_error(source, long_item)
        if gate_error is not None:
            code, message = gate_error
            v5.core.block(state, "short", code, message)
            state["short"]["status"] = "blocked"
            return v5.core.Action("blocked", message)
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
        long_state = self.github.newest_video_state() if hasattr(self.github, "newest_video_state") else {"version": 1, "items": []}
        long_verified = v5._newest(v5._verified_exact(long_state, source))
        long_candidate = None if long_verified else self._watchdog_candidate(long_state, source)

        stages = []
        if long_candidate is not None:
            stages.append(("long_video", v5.LONG_VIDEO_WORKFLOW, long_candidate, None))
        elif long_verified is not None:
            if (
                state.get("short", {}).get("status") == "complete"
                and state.get("short", {}).get("verified") is True
            ):
                return None
            short_state = self.github.newest_short_state()
            valid_short = [
                row
                for row in self._exact_short_items(short_state, source, long_item=long_verified)
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
            if stage_name == "long_video":
                run_id = stage.get("run_id")
                if run_id and stage.get("processed_run_id") != run_id and hasattr(self, "_workflow_run"):
                    completed_run = self._workflow_run(run_id)
                    if isinstance(completed_run, dict) and str(completed_run.get("status") or "") == "completed":
                        stage["processed_run_id"] = run_id
                        stage["last_run_conclusion"] = completed_run.get("conclusion")
                stage.update({
                    "item_id": item.get("id"),
                    "source_slug": source["slug"],
                    "source_content_sha256": source["content_sha256"],
                    "content_sha256": source["content_sha256"],
                    "source_id": item.get("source_id"),
                    "task_id": item.get("task_id"),
                    "provider_id": item.get("task_id"),
                    "artifact_id": item.get("artifact_id"),
                    "provider_status": item.get("last_provider_status") or item.get("status"),
                    "verified": False,
                })
                if stage.get("status") in {"complete", "uploaded"}:
                    stage["status"] = "generating"
            identity = f"{stage_name}:{source['slug']}:{item.get('id') or item.get('task_id') or 'unknown'}"
            watchdog.observe_media(
                stage,
                identity=identity,
                fingerprint=delivery_guard.media_fingerprint(item),
                provider_started_at=item.get("generation_started_at") or item.get("created_at"),
                now=self.now,
            )
            decision = watchdog.media_decision(stage, now=self.now)
            if decision == "hard_timeout":
                code = "LONG_VIDEO_PROVIDER_HARD_TIMEOUT" if stage_name == "long_video" else "SHORT_PROVIDER_HARD_TIMEOUT"
                minutes = int(watchdog.MEDIA_HARD_TIMEOUT.total_seconds() // 60)
                v5.core.block(
                    state,
                    stage_name,
                    code,
                    f"{stage_name} provider exceeded {minutes} minute hard timeout from launch/recovery",
                )
                stage["status"] = "blocked"
                self.github.save_controller_state(state)
                return v5.core.Action("blocked", f"{stage_name} provider hard timeout")

            active = self.github.active_workflow_run(workflow, production_only=True)
            if active:
                self.github.save_controller_state(state)
                return None

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

            if stage_name == "long_video":
                stage["status"] = "generating"
            v5.core.transition(
                state,
                f"{stage_name}_watchdog_wait",
                f"{stage_name} provider is pending; watchdog is waiting for durable progress before same-identity recovery",
                item_id=item.get("id"),
            )
            self.github.save_controller_state(state)
            return v5.core.Action("wait", f"{stage_name} provider pending under watchdog")
        return None

    def _ensure_article_public_and_deployed(self, state: dict) -> tuple[bool, v5.core.Action | None]:
        if getattr(self, "github", None) is None or getattr(self, "site", None) is None:
            return True, None
        posts = self.posts_on_main("main")
        todays = self._reconcile_existing_current_day_article(state, posts)
        if len(todays) > 1:
            v5.core.block(state, "article", "DUPLICATE_ARTICLE_DATE",
                          f"{len(todays)} articles share Israel date {self.now.date()}")
            return False, v5.core.Action("blocked", "duplicate published articles")
        if not todays:
            return True, None

        article = todays[0]
        slug = v5.core.canonical_slug(article)
        title = str(article.get("title") or "").strip()
        url = f"{v5.core.SITE_URL}/blog/{slug}"
        content_sha = str(state.get("article", {}).get("quality_content_sha256") or "").strip()

        if state.get("article", {}).get("_tick_live_verified"):
            return True, None

        status, page = self.site.get(url)
        is_pub = (status == 200 and v5.core.article_is_public(page, title, expected_slug=slug, expected_content_sha256=content_sha))
        if is_pub:
            state.setdefault("article", {}).update({
                "live": True,
                "live_verified_at": v5.core.utc_now(),
                "next_deploy_retry_at": None,
                "_tick_live_verified": True,
            })
            is_media_blocked = (
                (state.get("last_error") or {}).get("stage") in {"long_video", "short", "image", "video", "media"}
                or (state.get("long_video") or {}).get("status") in {"blocked", "exhausted"}
                or (state.get("short") or {}).get("status") in {"blocked", "exhausted"}
            )
            if not is_media_blocked and state.get("status") in {"blocked", "article_deploying", "article_deploy_wait", "article_generating", "article_retry_wait"}:
                v5.core.transition(state, "article_live", "HTTP 200 and expected title verified")
            return True, None

        state.setdefault("article", {})["live"] = False
        if self.github.active_workflow_run(v5.core.DEPLOY_WORKFLOW):
            v5.core.transition(state, "article_deploying", "deployment already active")
            return False, v5.core.Action("wait", "deployment active")

        pending_deploy = (state.get("pending_dispatches") or {}).get(v5.core.DEPLOY_WORKFLOW)
        if isinstance(pending_deploy, dict) and pending_deploy.get("cycle") == state.get("cycle"):
            if pending_deploy.get("status") in {"intent", "uncertain"}:
                v5.core.transition(state, "article_deploying", "deployment dispatch intent pending")
                return False, v5.core.Action("wait", "deployment dispatch pending reconciliation")
            if pending_deploy.get("status") == "dispatched":
                intent_dt = v5.core.parse_timestamp(pending_deploy.get("dispatched_at") or pending_deploy.get("intent_at"))
                if intent_dt is not None:
                    elapsed = (self.now.astimezone(v5.core.timezone.utc) - intent_dt).total_seconds()
                    if 0 <= elapsed < 180:
                        v5.core.transition(state, "article_deploying", "deployment dispatched; waiting for run visibility")
                        return False, v5.core.Action("wait", f"deployment dispatched {int(elapsed)}s ago; waiting for run visibility")

        next_deploy = v5.core.parse_timestamp(state["article"].get("next_deploy_retry_at"))
        if next_deploy and self.now.astimezone(v5.core.timezone.utc) < next_deploy:
            v5.core.transition(state, "article_deploy_wait", "deploy retry backoff is active",
                               retry_at=next_deploy.isoformat())
            return False, v5.core.Action("wait", f"deploy retry scheduled for {next_deploy.isoformat()}")

        attempts = int(state["article"].get("deploy_attempts") or 0) + 1
        self.github.dispatch(v5.core.DEPLOY_WORKFLOW)
        delay_index = max(1, attempts - v5.core.MAX_DEPLOY_ATTEMPTS_BEFORE_LONG_BACKOFF + 1)
        delay = 5 if attempts <= v5.core.MAX_DEPLOY_ATTEMPTS_BEFORE_LONG_BACKOFF else v5.core.article_retry_backoff_minutes(delay_index)
        state["article"].update({
            "deploy_attempts": attempts,
            "last_deploy_dispatch_at": v5.core.utc_now(),
            "next_deploy_retry_at": (
                v5.core.datetime.now(v5.core.timezone.utc) + v5.core.timedelta(minutes=delay)
            ).isoformat(),
        })
        v5.core.transition(
            state,
            "article_deploying",
            "public article check failed; recovery deploy dispatched",
            http_status=status,
            attempt=attempts,
        )
        return False, v5.core.Action("dispatch_deploy", "article not public yet")

    def tick(self):
        state = self.state()
        try:
            source = self._article_source(state)
            if (state.get("article") or {}).get("reconciled_existing_article") is True:
                self.github.save_controller_state(state)
        except v5.core.ControllerError as exc:
            code = str(exc).split(":", 1)[0]
            v5.core.block(state, "controller", code, str(exc))
            action = v5.core.Action("blocked", str(exc))
            _, deliverables = delivery_guard.delivery_contract(state)
            state["deliverables"] = deliverables
            self.github.save_controller_state(state)
            return state, action
        if source is not None:
            is_pub, deploy_action = self._ensure_article_public_and_deployed(state)
            if not is_pub and deploy_action is not None:
                _, deliverables = delivery_guard.delivery_contract(state)
                state["deliverables"] = deliverables
                self.github.save_controller_state(state)
                return state, deploy_action

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
