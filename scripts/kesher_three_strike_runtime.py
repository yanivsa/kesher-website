from __future__ import annotations

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
    """Overlay the Chief-of-Staff three-check contract on media stalls.

    The normal watchdog may poll every few minutes, but intervention strikes are
    counted at most once per Asia/Jerusalem hour and are scoped to
    pipeline_id + slug + content_sha256 + stage.
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
        state["direct_takeover_required"] = details
        v5.core.transition(
            state,
            state.get("status") or stage_name,
            "same Kesher incident remained stalled for three hourly checks; direct supervisor takeover required",
            **details,
        )
        self.github.save_controller_state(state)
        return v5.core.Action("direct_takeover_required", "three-strike threshold reached", details)

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
            watchdog_decision = watchdog.media_decision(stage, now=self.now)
            if watchdog_decision == "wait":
                self.github.save_controller_state(state)
                return v5.core.Action("wait", f"{stage_name} provider pending under watchdog")

            progress = self._intervention_progress(stage_name, source, item)
            hourly_token = intervention.jerusalem_hour_token(self.now)
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

            if watchdog_decision == "blocked" or decision.action == intervention.DIRECT_TAKEOVER:
                return self._direct_takeover(state, stage_name, source, item, decision)

            if decision.action == intervention.OBSERVE_CONTROLLER:
                v5.core.transition(
                    state,
                    f"{stage_name}_intervention_strike_1",
                    "durable stall detected; Controller gets one hourly window to recover the same identity",
                    incident_key=decision.incident_key,
                )
                self.github.save_controller_state(state)
                return v5.core.Action("wait", f"{stage_name} strike 1; Controller recovery window")

            if decision.action == intervention.WAIT_AFTER_CONTROLLER_ACTION:
                self.github.save_controller_state(state)
                return v5.core.Action("wait", f"{stage_name} strike 2; targeted Controller action already observed")

            if decision.action == intervention.FORCE_CONTROLLER_RECOVERY:
                active = self.github.active_workflow_run(workflow, production_only=True)
                if active:
                    stage["controller_recovery_required"] = {
                        "incident_key": decision.incident_key,
                        "strike": 2,
                        "active_run_id": active.get("id"),
                        "requested_at": v5.core.utc_now(),
                    }
                    v5.core.transition(
                        state,
                        f"{stage_name}_intervention_strike_2",
                        "same identity is still stalled; targeted Controller recovery required, but no duplicate dispatch while the child run is active",
                        incident_key=decision.incident_key,
                        active_run_id=active.get("id"),
                    )
                    self.github.save_controller_state(state)
                    return v5.core.Action("controller_recovery_required", f"{stage_name} strike 2; active child must be recovered in place")

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
