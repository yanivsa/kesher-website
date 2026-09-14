#!/usr/bin/env python3
"""Production Kesher V5 runtime with fail-closed quality and active supervision."""

from __future__ import annotations

import json
import os
import sys

if __package__:
    from . import article_claim_quality as quality
    from . import kesher_automation_policy as automation_policy
    from . import kesher_content_controller_v5 as v5
    from . import kesher_content_controller_v5_runtime as runtime
    from . import kesher_intervention_policy as intervention
    from . import kesher_jules_incident_repair as incident_repair
else:
    import article_claim_quality as quality
    import kesher_automation_policy as automation_policy
    import kesher_content_controller_v5 as v5
    import kesher_content_controller_v5_runtime as runtime
    import kesher_intervention_policy as intervention
    import kesher_jules_incident_repair as incident_repair


class StabilizedRuntimeV5Controller(runtime.RuntimeV5Controller):
    """Prevent invalid completion and enforce Controller → Jules → Direct supervision."""

    def _stamp_supervision_state(self, state):
        state["pipeline_id"] = "v5"
        state["supervision_contract_version"] = int(
            automation_policy.supervision_policy()["contract_version"]
        )
        source = self._article_source()
        if source is not None:
            state["source"] = dict(source)

    def _quality_preflight(self, state):
        posts = self.github.contents_json("src/data/posts.json", "main")
        if not isinstance(posts, list):
            raise v5.core.ControllerError("ARTICLE_SOURCE_INVALID")
        todays = v5.core.today_articles(posts, self.now.date())
        if len(todays) != 1:
            return None

        article = todays[0]
        source = v5.article_source_identity(article)
        state["source"] = dict(source)
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

        state["source"] = dict(source)
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

    @staticmethod
    def _incident_is_current(state, current):
        if str(current.get("pipeline_id") or "") != "v5":
            return False
        stage = str(current.get("stage") or "")
        if stage == "article":
            return str(current.get("slug") or "") == f"article-slot-{state.get('cycle')}"
        source = state.get("source") or {}
        return bool(
            stage in {"long_video", "short"}
            and str(current.get("slug") or "") == str(source.get("slug") or "")
            and str(current.get("content_sha256") or "") == str(source.get("content_sha256") or "")
        )

    def _pending_jules_incident(self, state):
        candidates = []
        for key, current in (state.get("interventions") or {}).items():
            if not isinstance(current, dict) or not self._incident_is_current(state, current):
                continue
            if int(current.get("strike_count") or 0) != 2:
                continue
            if current.get("owner") != "jules" or current.get("last_action") != intervention.ESCALATE_JULES:
                continue
            if isinstance(current.get("jules_repair"), dict) and current["jules_repair"].get("session_id"):
                continue
            candidates.append((str(current.get("last_observed_at") or ""), key, current))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        _, key, current = candidates[0]
        return key, current

    def _handoff_to_jules(self, state):
        pending = self._pending_jules_incident(state)
        if pending is None:
            return None
        incident_key, current = pending
        api_key = os.environ.get("JULES_API_KEY", "").strip()
        if not api_key:
            raise v5.core.ControllerError("JULES_API_KEY_MISSING_FOR_INCIDENT_REPAIR")

        stage_name = str(current.get("stage") or "")
        stage_state = state.get(stage_name) if isinstance(state.get(stage_name), dict) else {}
        if stage_name == "article":
            stage_state = state.get("article") or {}
        watchdog_state = stage_state.get("watchdog") if isinstance(stage_state, dict) else {}
        evidence = {
            "controller_status": state.get("status"),
            "last_error": state.get("last_error"),
            "stage_status": stage_state.get("status") if isinstance(stage_state, dict) else None,
            "item_id": stage_state.get("item_id") if isinstance(stage_state, dict) else None,
            "task_id": (
                stage_state.get("task_id") if isinstance(stage_state, dict) else None
            ) or ((watchdog_state or {}).get("session_id") if isinstance(watchdog_state, dict) else None),
            "provider_id": stage_state.get("provider_id") if isinstance(stage_state, dict) else None,
            "artifact_id": stage_state.get("artifact_id") if isinstance(stage_state, dict) else None,
            "source_id": stage_state.get("source_id") if isinstance(stage_state, dict) else None,
            "youtube_id": stage_state.get("youtube_id") if isinstance(stage_state, dict) else None,
            "youtube_url": stage_state.get("youtube_url") if isinstance(stage_state, dict) else None,
        }
        prompt = incident_repair.build_repair_prompt(
            pipeline_id="v5",
            slug=str(current.get("slug") or ""),
            content_sha256=str(current.get("content_sha256") or ""),
            stage=stage_name,
            failure_signature=str(current.get("failure_signature") or intervention.DEFAULT_FAILURE_SIGNATURE),
            idempotency_key=str(current.get("idempotency_key") or ""),
            evidence=evidence,
        )
        try:
            session_id = incident_repair.acquire_or_nudge_session(
                api_key=api_key,
                idempotency_key=str(current.get("idempotency_key") or ""),
                prompt=prompt,
            )
        except (incident_repair.IncidentRepairError, Exception) as exc:
            # Normalize transport/API failures into the controller's fail-closed path.
            raise v5.core.ControllerError(f"JULES_INCIDENT_REPAIR_FAILED: {exc}") from exc

        intervention.mark_jules_action(
            state,
            incident_key=incident_key,
            session_id=session_id,
            now=self.now,
        )
        v5.core.transition(
            state,
            state.get("status") or stage_name,
            "S2 supervisor handed exact stalled Kesher incident directly to Jules",
            incident_key=incident_key,
            jules_session_id=session_id,
            stage=stage_name,
        )
        self.github.save_controller_state(state)
        return v5.core.Action(
            "jules_incident_repair",
            "same exact incident persisted into S2; Jules repair session acquired",
            {"session_id": session_id, "incident_key": incident_key},
        )

    def tick(self):
        state = self.state()
        self._stamp_supervision_state(state)
        blocker = self._quality_preflight(state)
        if blocker is not None:
            self.github.save_controller_state(state)
            return state, blocker

        self._overview_evidence_preflight(state)
        self.github.save_controller_state(state)
        state, action = super().tick()
        self._stamp_supervision_state(state)
        jules_action = self._handoff_to_jules(state)
        self.github.save_controller_state(state)
        return state, jules_action or action


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
