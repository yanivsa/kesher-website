from __future__ import annotations

import hashlib
from typing import Any

if __package__:
    from . import kesher_content_controller_v5 as v5
    from . import kesher_content_watchdog as watchdog
    from . import kesher_e2e_delivery_guard as delivery_guard
    from . import kesher_intervention_policy as intervention
else:
    import kesher_content_controller_v5 as v5
    import kesher_content_watchdog as watchdog
    import kesher_e2e_delivery_guard as delivery_guard
    import kesher_intervention_policy as intervention


class ThreeStrikeMediaInterventionMixin:
    """Overlay the Chief-of-Staff three-check contract on Kesher stalls.

    The production Controller keeps its fast, bounded recovery cadence. The
    intervention layer runs at most once per Asia/Jerusalem hour and asks a
    separate question: did the same work identity make durable progress? If
    not, the third hourly check requires direct supervisor takeover.
    """

    PIPELINE_ID = "v5"

    @staticmethod
    def _intervention_progress(stage_name: str, source: dict[str, str], item: dict[str, Any]) -> dict[str, Any]:
        media = item.get("media") or {}
        return {
            "stage": stage_name,
            "status": item.get("status"),
            "slug": source["slug"],
            "content_sha256": source["content_sha256"],
            "item_id": item.get("id"),
            "task_id": item.get("task_id"),
            "provider_id": item.get("task_id"),
            "artifact_id": item.get("artifact_id"),
            "source_id": item.get("source_id"),
            "youtube_id": item.get("youtube_id"),
            "youtube_url": item.get("youtube_url"),
            "verified": item.get("verified") is True or item.get("uploaded") is True,
            "portrait_verified": item.get("portrait_verified") is True,
            "signature_verified": item.get("signature_verified") is True,
            "width": media.get("width"),
            "height": media.get("height"),
        }

    @staticmethod
    def _controller_action_token(stage: dict[str, Any]) -> str | None:
        current = stage.get("watchdog")
        if not isinstance(current, dict):
            return None
        count = int(current.get("recovery_count") or 0)
        at = str(current.get("last_recovery_at") or "")
        if not count and not at:
            return None
        return f"recovery:{count}:{at}"

    @staticmethod
    def _article_intervention_source(slot: str) -> dict[str, str]:
        """Stable pre-publication identity before a real slug/content SHA exists."""
        seed = f"kesher-prepublication:{slot}"
        return {
            "slug": f"article-slot-{slot}",
            "content_sha256": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        }

    @staticmethod
    def _article_controller_action_token(stage: dict[str, Any]) -> str | None:
        current = stage.get("watchdog")
        if not isinstance(current, dict):
            return None
        nudge_count = int(current.get("nudge_count") or 0)
        restart_count = int(current.get("worker_restart_count") or 0)
        nudge_at = str(current.get("last_nudge_at") or "")
        restart_at = str(current.get("last_restart_at") or "")
        if not (nudge_count or restart_count or nudge_at or restart_at):
            return None
        return f"nudge:{nudge_count}:{nudge_at}|restart:{restart_count}:{restart_at}"

    @staticmethod
    def _article_intervention_progress(state: dict[str, Any], source: dict[str, str]) -> dict[str, Any]:
        article = state.get("article") or {}
        current = article.get("watchdog") or {}
        session_id = current.get("session_id")
        return {
            "stage": "article",
            # Controller status transitions such as nudge/restart are activity,
            # not durable article progress. Keep this status deliberately stable.
            "status": "article_session",
            "slug": source["slug"],
            "content_sha256": source["content_sha256"],
            "task_id": session_id,
            "provider_id": session_id,
            # The Jules session fingerprint changes only when its durable state,
            # outputs or PR URLs change; this is the article progress signal.
            "source_id": current.get("last_fingerprint"),
            "artifact_id": article.get("pr_number") or article.get("pr_url"),
        }

    @staticmethod
    def _clear_takeover_if_recovered(state, stage, incident_key: str) -> None:
        takeover = state.get("direct_takeover_required")
        if isinstance(takeover, dict) and takeover.get("incident_key") == incident_key:
            state.pop("direct_takeover_required", None)
        stage.pop("controller_recovery_required", None)

    def _direct_takeover(self, state, stage_name, source, item, decision):
        details = {
            "pipeline_id": self.PIPELINE_ID,
            "incident_key": decision.incident_key,
            "strike": decision.strike,
            "stage": stage_name,
            "slug": source["slug"],
            "content_sha256": source["content_sha256"],
            "item_id": item.get("id"),
            "task_id": item.get("task_id"),
            "required": True,
        }
        existing = state.get("direct_takeover_required")
        if not (isinstance(existing, dict) and existing.get("incident_key") == decision.incident_key and existing.get("required") is True):
            state["direct_takeover_required"] = details
            v5.core.transition(
                state,
                state.get("status") or stage_name,
                "same Kesher incident remained stalled for three hourly checks; direct supervisor takeover required",
                **details,
            )
        self.github.save_controller_state(state)
        return v5.core.Action("direct_takeover_required", "three-strike threshold reached", details)

    def _article_watchdog(self, state: dict[str, Any]):
        """Keep V5's fast article recovery, with hourly direct-takeover ownership."""
        posts = self.github.contents_json("src/data/posts.json", "main")
        if not isinstance(posts, list) or v5.core.today_articles(posts, self.now.date()):
            return None
        slot = self.now.date().isoformat()
        if self.github.open_article_prs(slot):
            return None
        active = self.github.active_workflow_run(v5.core.ARTICLE_WORKFLOW)
        if not active:
            return None

        snapshot_getter = getattr(self.github, "article_session_snapshot", None)
        snapshot = snapshot_getter(slot) if snapshot_getter is not None else None
        session_id = str((snapshot or {}).get("session_id") or "").strip() or None
        fingerprint = str((snapshot or {}).get("fingerprint") or "").strip() or None
        watchdog.observe_article(
            state["article"],
            identity=slot,
            run_started_at=active.get("run_started_at") or active.get("created_at"),
            session_id=session_id,
            fingerprint=fingerprint,
            now=self.now,
        )
        state["article"]["run_id"] = active.get("id")
        watchdog_decision = watchdog.article_decision(
            state["article"], now=self.now, active_run_id=active.get("id")
        )

        source = self._article_intervention_source(slot)
        progress = self._article_intervention_progress(state, source)
        incident_key = intervention.incident_key(
            pipeline_id=self.PIPELINE_ID,
            slug=source["slug"],
            content_sha256=source["content_sha256"],
            stage="article",
        )
        existing = (state.get("interventions") or {}).get(incident_key)
        current_watchdog = state["article"].get("watchdog") or {}
        recovery_already_started = bool(
            int(current_watchdog.get("nudge_count") or 0)
            or int(current_watchdog.get("worker_restart_count") or 0)
            or current_watchdog.get("last_nudge_at")
            or current_watchdog.get("last_restart_at")
        )
        is_stalled = watchdog_decision != "wait" or isinstance(existing, dict) or recovery_already_started

        decision = None
        if is_stalled:
            decision = intervention.observe_incident(
                state=state,
                pipeline_id=self.PIPELINE_ID,
                slug=source["slug"],
                content_sha256=source["content_sha256"],
                stage="article",
                progress=progress,
                check_token=intervention.jerusalem_hour_token(self.now),
                controller_action_token=self._article_controller_action_token(state["article"]),
                now=self.now,
            )
            if decision.progress_reset:
                self._clear_takeover_if_recovered(state, state["article"], incident_key)
                v5.core.transition(
                    state,
                    "article_generating",
                    "Jules made durable progress; article intervention strikes reset",
                    session_id=session_id,
                )
                return v5.core.Action("wait", "article made durable Jules progress")
            if decision.action == intervention.DIRECT_TAKEOVER:
                return self._direct_takeover(
                    state,
                    "article",
                    source,
                    {"id": active.get("id"), "task_id": session_id},
                    decision,
                )

        if watchdog_decision == "nudge":
            self.github.nudge_article_session(session_id)
            watchdog.mark_article_nudge(state["article"], now=self.now)
            v5.core.transition(
                state,
                "article_watchdog_nudge",
                "article stalled; nudged authoritative Jules session",
                session_id=session_id,
            )
            if decision is not None:
                intervention.mark_controller_action(
                    state,
                    incident_key=decision.incident_key,
                    action_token=self._article_controller_action_token(state["article"]) or "article-nudge",
                    now=self.now,
                )
            return v5.core.Action("article_watchdog_nudge", "nudged same Jules article session")

        if watchdog_decision == "restart":
            run_id = active.get("id")
            self.github.cancel_workflow_run(run_id)
            self.github.dispatch(v5.core.ARTICLE_WORKFLOW, {"slot": slot})
            watchdog.mark_article_restart(state["article"], now=self.now, run_id=run_id)
            state["article"]["run_id"] = None
            v5.core.transition(
                state,
                "article_watchdog_restart",
                "article stalled after nudge; restarted GitHub worker for same Jules slot/session",
                session_id=session_id,
                cancelled_run_id=run_id,
            )
            if decision is not None:
                intervention.mark_controller_action(
                    state,
                    incident_key=decision.incident_key,
                    action_token=self._article_controller_action_token(state["article"]) or f"article-restart:{run_id}",
                    now=self.now,
                )
            return v5.core.Action(
                "article_watchdog_restart",
                "restarted article worker for same slot/session",
                {"slot": slot},
            )

        if watchdog_decision == "blocked":
            # The Controller has exhausted its own bounded retries. Do not create
            # more work identities. The hourly supervisor still owns the third
            # check and will take over directly when its threshold is reached.
            state["article"]["controller_recovery_required"] = {
                "incident_key": decision.incident_key if decision else incident_key,
                "reason": "article watchdog recovery budget exhausted",
                "requested_at": v5.core.utc_now(),
            }
            v5.core.transition(
                state,
                "article_watchdog_exhausted_wait",
                "article Controller recovery budget exhausted; preserving same identity for three-strike supervisor",
                session_id=session_id,
            )
            return v5.core.Action("wait", "article Controller recovery exhausted; supervisor tracking continues")

        v5.core.transition(
            state,
            "article_generating",
            "article workflow active; watchdog observing progress",
            session_id=session_id,
        )
        return v5.core.Action("wait", "article workflow active")

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
            identity = f"{stage_name}:{source['slug']}:{source['content_sha256']}:{item.get('id') or item.get('task_id') or 'unknown'}"
            watchdog.observe_media(
                stage,
                identity=identity,
                fingerprint=delivery_guard.media_fingerprint(item),
                now=self.now,
            )

            progress = self._intervention_progress(stage_name, source, item)
            hourly_token = intervention.jerusalem_hour_token(self.now)
            incident_key = intervention.incident_key(
                pipeline_id=self.PIPELINE_ID,
                slug=source["slug"],
                content_sha256=source["content_sha256"],
                stage=stage_name,
            )
            existing_incident = (state.get("interventions") or {}).get(incident_key)
            if isinstance(existing_incident, dict):
                current_fingerprint = intervention.durable_progress_fingerprint(progress)
                if current_fingerprint != str(existing_incident.get("last_fingerprint") or ""):
                    reset = intervention.observe_incident(
                        state=state,
                        pipeline_id=self.PIPELINE_ID,
                        slug=source["slug"],
                        content_sha256=source["content_sha256"],
                        stage=stage_name,
                        progress=progress,
                        check_token=hourly_token,
                        controller_action_token=self._controller_action_token(stage),
                        now=self.now,
                    )
                    if reset.progress_reset:
                        self._clear_takeover_if_recovered(state, stage, incident_key)
                        self.github.save_controller_state(state)
                        return v5.core.Action("wait", f"{stage_name} made durable progress; intervention strikes reset")

            watchdog_decision = watchdog.media_decision(stage, now=self.now)
            if watchdog_decision == "wait":
                self.github.save_controller_state(state)
                return v5.core.Action("wait", f"{stage_name} provider pending under watchdog")

            decision = intervention.observe_incident(
                state=state,
                pipeline_id=self.PIPELINE_ID,
                slug=source["slug"],
                content_sha256=source["content_sha256"],
                stage=stage_name,
                progress=progress,
                check_token=hourly_token,
                controller_action_token=self._controller_action_token(stage),
                now=self.now,
            )

            if decision.action == intervention.DIRECT_TAKEOVER:
                return self._direct_takeover(state, stage_name, source, item, decision)

            if watchdog_decision == "blocked":
                stage["controller_recovery_required"] = {
                    "incident_key": decision.incident_key,
                    "strike": decision.strike,
                    "reason": "media watchdog recovery budget exhausted",
                    "requested_at": v5.core.utc_now(),
                }
                self.github.save_controller_state(state)
                return v5.core.Action("wait", f"{stage_name} Controller recovery exhausted; supervisor tracking continues")

            if decision.action == intervention.WAIT_AFTER_CONTROLLER_ACTION:
                self.github.save_controller_state(state)
                return v5.core.Action("wait", f"{stage_name} strike {decision.strike}; targeted Controller action already observed")

            if decision.action in {intervention.OBSERVE_CONTROLLER, intervention.FORCE_CONTROLLER_RECOVERY}:
                active = self.github.active_workflow_run(workflow, production_only=True)
                if active:
                    if decision.action == intervention.FORCE_CONTROLLER_RECOVERY:
                        stage["controller_recovery_required"] = {
                            "incident_key": decision.incident_key,
                            "strike": 2,
                            "active_run_id": active.get("id"),
                            "requested_at": v5.core.utc_now(),
                        }
                    self.github.save_controller_state(state)
                    return v5.core.Action("wait", f"{stage_name} same-identity child is already active; no duplicate dispatch")

                action = (
                    self._recover_long_video(state, source, item)
                    if stage_name == "long_video"
                    else self._recover_short(state, source, item, long_item)
                )
                action_token = self._controller_action_token(stage) or f"dispatch:{hourly_token}"
                intervention.mark_controller_action(
                    state,
                    incident_key=decision.incident_key,
                    action_token=action_token,
                    now=self.now,
                )
                stage.pop("controller_recovery_required", None)
                self.github.save_controller_state(state)
                return action

            self.github.save_controller_state(state)
            return v5.core.Action("wait", f"{stage_name} intervention policy waiting")
        return None
