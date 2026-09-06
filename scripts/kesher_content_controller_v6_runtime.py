#!/usr/bin/env python3
"""Isolated Kesher V6 intervention/reconciliation foundation.

V6 is intentionally not production-dispatching yet. It owns an independent
pipeline/state namespace and shares only the deterministic intervention policy.
This makes it safe to validate in shadow/manual mode before a Canary enables
article/media provider dispatches.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, MutableMapping

if __package__:
    from . import kesher_intervention_policy as intervention
else:
    import kesher_intervention_policy as intervention

PIPELINE_ID = "v6"
STATE_REF = "automation-state-v6"
ARTIFACT_NAMESPACE = "kesher-v6"
CONCURRENCY_GROUP = "kesher-content-controller-v6"


class V6InterventionReconciler:
    """V6-facing adapter for the shared three-check intervention contract."""

    def __init__(self, state: MutableMapping[str, Any]):
        self.state = state
        self.state.setdefault("pipeline_id", PIPELINE_ID)
        self.state.setdefault("state_ref", STATE_REF)
        self.state.setdefault("artifact_namespace", ARTIFACT_NAMESPACE)

    def observe(
        self,
        *,
        slug: str,
        content_sha256: str,
        stage: str,
        progress: dict[str, Any],
        check_token: str,
        controller_action_token: str | None,
        now: datetime,
    ) -> intervention.InterventionDecision:
        return intervention.observe_incident(
            state=self.state,
            pipeline_id=PIPELINE_ID,
            slug=slug,
            content_sha256=content_sha256,
            stage=stage,
            progress=progress,
            check_token=check_token,
            controller_action_token=controller_action_token,
            now=now,
        )


def _self_check() -> dict[str, Any]:
    """Return machine-readable isolation evidence without dispatching providers."""
    state: dict[str, Any] = {}
    reconciler = V6InterventionReconciler(state)
    now = datetime.now(timezone.utc)
    decision = reconciler.observe(
        slug="v6-self-check",
        content_sha256="self-check-sha",
        stage="validation",
        progress={"stage": "validation", "status": "pending"},
        check_token=intervention.jerusalem_hour_token(now),
        controller_action_token=None,
        now=now,
    )
    return {
        "pipeline_id": PIPELINE_ID,
        "state_ref": STATE_REF,
        "artifact_namespace": ARTIFACT_NAMESPACE,
        "concurrency_group": CONCURRENCY_GROUP,
        "production_dispatch_enabled": False,
        "intervention_action": decision.action,
        "strike": decision.strike,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--report-json", action="store_true")
    args = parser.parse_args()
    if not (args.self_check or args.report_json):
        parser.error("V6 is shadow/manual only; use --self-check or --report-json")
    print(json.dumps(_self_check(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
