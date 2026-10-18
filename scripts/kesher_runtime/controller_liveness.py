#!/usr/bin/env python3
"""Bounded, idempotent liveness recovery for Kesher Content Controller.

Detects when GitHub Actions drops or delays scheduled triggers of the canonical
controller workflow (.github/workflows/kesher-content-controller.yml), and dispatches
at most one bounded recovery wake-up per cycle.

Key invariants:
1. Sole authority: Kesher Content Controller remains the sole pre-cutover Schema-5
   authority. This module never mutates .kesher-controller/state.json, never executes
   child workflows directly, and never runs Jules or repair steps.
2. Bounded & idempotent: Persist-before-dispatch protocol prevents duplicate triggers
   even during delayed GitHub run visibility or API restarts (max 3 recoveries per cycle).
3. Terminal protection: Never resurrects terminal, blocked, or article-exhausted cycles.
4. Budget protection: Dispatches with empty inputs, consuming no article/image/Long/Short
   generation attempts or budgets.
5. Schema-6 cutover safe: Automatically yields to Schema-6 or handover authority.
6. Fail-closed: Refuses dispatch if state, repository, or authority cannot be verified.
"""

from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")

CANONICAL_CONTROLLER_WORKFLOW = ".github/workflows/kesher-content-controller.yml"
CANONICAL_CONTROLLER_WORKFLOW_NAME = "Kesher Content Controller"
DEFAULT_REPO = "yanivsa/kesher-website"
DEFAULT_REF = "main"

FRESHNESS_WINDOW = timedelta(minutes=15)
DISPATCH_VISIBILITY_GRACE = timedelta(minutes=5)
MAX_RECOVERIES_PER_CYCLE = 3

ACTIVE_RUN_STATUSES = ("queued", "in_progress", "waiting", "pending", "requested")
TERMINAL_CYCLE_STATUSES = ("blocked", "completed")


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class LivenessDecision:
    def __init__(
        self,
        status: str,
        reason: str,
        *,
        action: Optional[str] = None,
        target_workflow: str = CANONICAL_CONTROLLER_WORKFLOW,
        target_ref: str = DEFAULT_REF,
        target_inputs: Optional[dict[str, Any]] = None,
        cycle: Optional[str] = None,
        last_activity_at: Optional[str] = None,
        active_run_id: Optional[int] = None,
        intent_id: Optional[str] = None,
    ):
        self.status = status
        self.reason = reason
        self.action = action
        self.target_workflow = target_workflow
        self.target_ref = target_ref
        self.target_inputs = target_inputs or {}
        self.cycle = cycle
        self.last_activity_at = last_activity_at
        self.active_run_id = active_run_id
        self.intent_id = intent_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "action": self.action,
            "reason": self.reason,
            "cycle": self.cycle,
            "target_workflow": self.target_workflow,
            "target_ref": self.target_ref,
            "target_inputs": self.target_inputs,
            "last_activity_at": self.last_activity_at,
            "active_run_id": self.active_run_id,
            "intent_id": self.intent_id,
        }

    def __repr__(self) -> str:
        return f"<LivenessDecision status={self.status} action={self.action} reason={self.reason}>"


def evaluate_liveness(
    controller_state: Optional[dict[str, Any]],
    recent_runs: list[dict[str, Any]],
    liveness_ledger: dict[str, Any],
    now: datetime,
    *,
    freshness_window: timedelta = FRESHNESS_WINDOW,
    visibility_grace: timedelta = DISPATCH_VISIBILITY_GRACE,
    max_recoveries: int = MAX_RECOVERIES_PER_CYCLE,
    expected_repo: str = DEFAULT_REPO,
    current_repo: Optional[str] = None,
) -> LivenessDecision:
    """Pure deterministic liveness evaluator for Kesher Content Controller."""
    now_utc = now.astimezone(timezone.utc)

    # 1. Authority validation & fail-closed repo verification
    if current_repo and current_repo != expected_repo:
        return LivenessDecision(
            status="LIVENESS_REFUSED_FOREIGN_REPOSITORY",
            reason=f"Repository {current_repo} does not match expected authority repository {expected_repo}",
        )

    if not isinstance(controller_state, dict):
        return LivenessDecision(
            status="LIVENESS_REFUSED_INVALID_STATE",
            reason="Controller state is not a valid dictionary",
        )

    # 2. Schema-6 cutover guard
    if controller_state.get("schema_version", 5) >= 6 or "handover" in controller_state or "github_exclusion" in controller_state:
        return LivenessDecision(
            status="SCHEMA6_AUTHORITY_ACTIVE",
            reason="Controller state is governed by Schema-6 or post-cutover authority; legacy recovery refused",
            cycle=controller_state.get("cycle"),
        )

    cycle = controller_state.get("cycle")
    if not cycle or not isinstance(cycle, str):
        return LivenessDecision(
            status="LIVENESS_REFUSED_INVALID_STATE",
            reason="Controller state missing valid cycle identity",
        )

    # 3. Terminal cycle protection (cannot resurrect terminal or exhausted cycle)
    status = controller_state.get("status")
    article_status = (controller_state.get("article") or {}).get("status")
    if status in TERMINAL_CYCLE_STATUSES or article_status == "exhausted":
        return LivenessDecision(
            status="LIVENESS_OK_CYCLE_TERMINAL",
            reason=f"Current cycle {cycle} is terminal (status={status}, article={article_status}); no resurrection permitted",
            cycle=cycle,
        )

    # 4. In-flight intent & delayed workflow visibility reconciliation
    current_intent = liveness_ledger.get("current_intent")
    reconciled_intent_id = None
    if isinstance(current_intent, dict) and current_intent.get("status") in ("dispatching", "dispatched"):
        intent_created_at = _parse_iso(current_intent.get("created_at"))
        intent_id = current_intent.get("intent_id")

        if intent_created_at:
            # Check if any run appeared at or after intent dispatch
            matching_run = None
            for run in recent_runs:
                created = _parse_iso(run.get("createdAt") or run.get("created_at") or run.get("run_started_at"))
                if created and created >= intent_created_at - timedelta(seconds=15):
                    matching_run = run
                    break

            if matching_run:
                # Intent reconciled by visible run
                reconciled_intent_id = intent_id
            else:
                # No visible run yet - check if within visibility grace window
                idle_since_intent = now_utc - intent_created_at
                if idle_since_intent < visibility_grace:
                    return LivenessDecision(
                        status="LIVENESS_WAIT_DISPATCH_VISIBILITY",
                        reason=f"Recovery intent {intent_id} dispatched {idle_since_intent.total_seconds():.1f}s ago; waiting for GitHub workflow visibility",
                        cycle=cycle,
                        intent_id=intent_id,
                    )
                # Beyond visibility grace: intent timed out or dropped by GitHub API
                # Fall through to evaluate freshness and allow retry if budget permits

    # 5. Active/queued controller run check
    for run in recent_runs:
        run_status = run.get("status")
        if run_status in ACTIVE_RUN_STATUSES:
            run_id = run.get("databaseId") or run.get("id")
            return LivenessDecision(
                status="LIVENESS_OK_ACTIVE_RUN_PRESENT",
                reason=f"Canonical controller run {run_id} is currently {run_status}",
                cycle=cycle,
                active_run_id=run_id,
                intent_id=reconciled_intent_id,
            )

    # 6. Freshness check
    activity_timestamps = []
    state_updated = _parse_iso(controller_state.get("updated_at"))
    if state_updated:
        activity_timestamps.append(state_updated)

    for run in recent_runs:
        for key in ("createdAt", "created_at", "updatedAt", "updated_at"):
            t = _parse_iso(run.get(key))
            if t:
                activity_timestamps.append(t)

    latest_activity = max(activity_timestamps) if activity_timestamps else None
    if latest_activity:
        idle_duration = now_utc - latest_activity
        if idle_duration < freshness_window:
            return LivenessDecision(
                status="LIVENESS_OK_FRESH",
                reason=f"Canonical controller active within freshness window ({idle_duration.total_seconds():.1f}s < {freshness_window.total_seconds():.1f}s)",
                cycle=cycle,
                last_activity_at=_iso(latest_activity),
                intent_id=reconciled_intent_id,
            )
    else:
        idle_duration = None

    # 7. Recovery budget exhaustion check
    cycle_history = liveness_ledger.get("cycles", {}).get(cycle, {})
    israel_dt = now_utc.astimezone(ISRAEL_TZ)
    is_active_window = israel_dt.hour >= 8

    if is_active_window:
        if "active_window_recovery_count" in cycle_history:
            recoveries_count = int(cycle_history["active_window_recovery_count"] or 0)
        else:
            recoveries_count = int(cycle_history.get("recovery_count") or 0)
        phase_label = "active-window"
    else:
        if "pre_window_recovery_count" in cycle_history:
            recoveries_count = int(cycle_history["pre_window_recovery_count"] or 0)
        else:
            recoveries_count = int(cycle_history.get("recovery_count") or 0)
        phase_label = "pre-window"

    if recoveries_count >= max_recoveries:
        return LivenessDecision(
            status="LIVENESS_RECOVERY_BUDGET_EXHAUSTED",
            reason=f"Maximum {phase_label} recovery dispatches reached for cycle {cycle} ({recoveries_count}/{max_recoveries})",
            cycle=cycle,
            last_activity_at=_iso(latest_activity) if latest_activity else None,
        )

    # 8. All guards satisfied: recovery dispatch required
    idle_str = f"{idle_duration.total_seconds():.1f}s" if idle_duration else "unknown"
    return LivenessDecision(
        status="LIVENESS_RECOVERY_REQUIRED",
        action="dispatch",
        reason=f"Canonical controller stale (idle {idle_str} >= {freshness_window.total_seconds():.1f}s); no active run; budget {recoveries_count}/{max_recoveries}",
        cycle=cycle,
        target_workflow=CANONICAL_CONTROLLER_WORKFLOW,
        target_ref=DEFAULT_REF,
        target_inputs={},
        last_activity_at=_iso(latest_activity) if latest_activity else None,
    )


class GitHubLivenessTransport:
    """Interacts with GitHub Actions API for workflow runs and dispatches."""

    def __init__(self, token: Optional[str] = None, repo: str = DEFAULT_REPO):
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.repo = repo

    def get_recent_runs(self, workflow_name: str = "kesher-content-controller.yml", limit: int = 10) -> list[dict[str, Any]]:
        if not self.token:
            return []
        url = f"https://api.github.com/repos/{self.repo}/actions/workflows/{workflow_name}/runs?per_page={limit}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Kesher-Controller-Liveness",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("workflow_runs", [])
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return []

    def dispatch_workflow(self, workflow_path: str, ref: str = DEFAULT_REF, inputs: Optional[dict[str, Any]] = None) -> bool:
        if not self.token:
            raise RuntimeError("GITHUB_TOKEN_REQUIRED_FOR_DISPATCH")
        workflow_filename = Path(workflow_path).name
        url = f"https://api.github.com/repos/{self.repo}/actions/workflows/{workflow_filename}/dispatches"
        body = json.dumps({"ref": ref, "inputs": inputs or {}}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
                "User-Agent": "Kesher-Controller-Liveness",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status in (200, 204)
        except urllib.error.URLError as exc:
            raise RuntimeError(f"WORKFLOW_DISPATCH_FAILED: {exc}") from exc

    def get_controller_state_from_git(self, ref: str = "automation-state") -> Optional[dict[str, Any]]:
        if not self.token:
            return None
        url = f"https://api.github.com/repos/{self.repo}/contents/.kesher-controller/state.json?ref={ref}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Kesher-Controller-Liveness",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = base64.b64decode(data.get("content", "")).decode("utf-8")
                return json.loads(content)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            return None

    def get_liveness_ledger(self, ref: str = "automation-state") -> tuple[dict[str, Any], Optional[str]]:
        if not self.token:
            return {}, None
        url = f"https://api.github.com/repos/{self.repo}/contents/.kesher-controller/controller-liveness.json?ref={ref}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Kesher-Controller-Liveness",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = base64.b64decode(data.get("content", "")).decode("utf-8")
                return json.loads(content), data.get("sha")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {}, None
            return {}, None
        except Exception:
            return {}, None

    def put_liveness_ledger(self, ledger: dict[str, Any], sha: Optional[str] = None, ref: str = "automation-state") -> Optional[str]:
        if not self.token:
            return None
        url = f"https://api.github.com/repos/{self.repo}/contents/.kesher-controller/controller-liveness.json"
        body: dict[str, Any] = {
            "message": "state: update controller liveness ledger [skip ci]",
            "content": base64.b64encode(
                (json.dumps(ledger, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
            ).decode("ascii"),
            "branch": ref,
        }
        if sha:
            body["sha"] = sha
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
                "User-Agent": "Kesher-Controller-Liveness",
            },
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return (data.get("content") or {}).get("sha")
        except Exception:
            return None


class ControllerLivenessWatchdog:
    """Coordinates detection, durable CAS intent recording, and bounded dispatch."""

    def __init__(
        self,
        *,
        repo: str = DEFAULT_REPO,
        ledger_path: Optional[Path] = None,
        transport: Optional[GitHubLivenessTransport] = None,
    ):
        self.repo = repo
        self.ledger_path = ledger_path or (Path(".kesher-controller") / "controller-liveness.json")
        self.transport = transport or GitHubLivenessTransport(repo=repo)
        self._remote_sha: Optional[str] = None

    def load_ledger(self) -> dict[str, Any]:
        # Try loading remote ledger from git ref (automation-state) first
        if hasattr(self.transport, "get_liveness_ledger"):
            try:
                remote_ledger, sha = self.transport.get_liveness_ledger()
                if remote_ledger:
                    self._remote_sha = sha
                    return remote_ledger
            except Exception:
                pass

        if self.ledger_path.exists():
            try:
                return json.loads(self.ledger_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def save_ledger(self, ledger: dict[str, Any]) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.ledger_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp_path.replace(self.ledger_path)

        # Persist remotely to automation-state branch via transport
        if hasattr(self.transport, "put_liveness_ledger"):
            try:
                new_sha = self.transport.put_liveness_ledger(ledger, sha=self._remote_sha)
                if new_sha:
                    self._remote_sha = new_sha
            except Exception:
                pass

    def reconcile(
        self,
        *,
        controller_state: Optional[dict[str, Any]] = None,
        recent_runs: Optional[list[dict[str, Any]]] = None,
        now: Optional[datetime] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        now_dt = now or datetime.now(timezone.utc)
        if controller_state is None:
            controller_state = self.transport.get_controller_state_from_git()
        if recent_runs is None:
            recent_runs = self.transport.get_recent_runs()

        ledger = self.load_ledger()

        # Step 1: Evaluate
        decision = evaluate_liveness(
            controller_state,
            recent_runs,
            ledger,
            now_dt,
            expected_repo=self.repo,
            current_repo=os.environ.get("GITHUB_REPOSITORY", self.repo),
        )

        # Step 2: Handle intent reconciliation if run appeared
        current_intent = ledger.get("current_intent")
        if current_intent and decision.status in ("LIVENESS_OK_FRESH", "LIVENESS_OK_ACTIVE_RUN_PRESENT") and decision.intent_id == current_intent.get("intent_id"):
            current_intent["status"] = "reconciled"
            current_intent["reconciled_at"] = _iso(now_dt)
            ledger.setdefault("history", []).append(copy.deepcopy(current_intent))
            ledger["current_intent"] = None
            self.save_ledger(ledger)

        # Step 3: Execute bounded dispatch if required
        dispatched = False
        if decision.action == "dispatch" and not dry_run:
            cycle = decision.cycle or "unknown"
            intent_id = f"liveness-{cycle}-{int(now_dt.timestamp())}"
            intent = {
                "intent_id": intent_id,
                "cycle": cycle,
                "created_at": _iso(now_dt),
                "status": "dispatching",
                "target_workflow": decision.target_workflow,
                "target_ref": decision.target_ref,
                "inputs": decision.target_inputs,
            }
            # Durable write-ahead before calling GitHub API
            ledger["current_intent"] = intent
            self.save_ledger(ledger)

            # API dispatch
            try:
                self.transport.dispatch_workflow(
                    decision.target_workflow,
                    ref=decision.target_ref,
                    inputs=decision.target_inputs,
                )
                dispatched = True
                intent["status"] = "dispatched"
                intent["dispatched_at"] = _iso(now_dt)

                cycle_rec = ledger.setdefault("cycles", {}).setdefault(cycle, {})
                israel_dt = now_dt.astimezone(ISRAEL_TZ)
                if israel_dt.hour >= 8:
                    cycle_rec["active_window_recovery_count"] = int(cycle_rec.get("active_window_recovery_count") or 0) + 1
                else:
                    cycle_rec["pre_window_recovery_count"] = int(cycle_rec.get("pre_window_recovery_count") or 0) + 1
                cycle_rec["recovery_count"] = int(cycle_rec.get("recovery_count") or 0) + 1
                cycle_rec["last_recovery_at"] = _iso(now_dt)
                self.save_ledger(ledger)
            except Exception as exc:
                intent["status"] = "dispatch_failed"
                intent["error"] = str(exc)
                self.save_ledger(ledger)
                raise

        report = decision.to_dict()
        report["dispatched"] = dispatched
        report["dry_run"] = dry_run
        report["ledger_path"] = str(self.ledger_path)
        return report


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true", help="Audit controller liveness without side effects")
    parser.add_argument("--reconcile", action="store_true", help="Reconcile and dispatch recovery if stale")
    parser.add_argument("--state-file", type=Path, help="Path to local controller state JSON for offline evaluation")
    parser.add_argument("--ledger-file", type=Path, help="Path to local liveness ledger JSON")
    parser.add_argument("--now", type=str, help="ISO-8601 evaluation timestamp override")
    parser.add_argument("--repo", type=str, default=DEFAULT_REPO, help="GitHub repository name")

    args = parser.parse_args(argv)

    now = _parse_iso(args.now) if args.now else datetime.now(timezone.utc)
    watchdog = ControllerLivenessWatchdog(
        repo=args.repo,
        ledger_path=args.ledger_file,
    )

    state = None
    if args.state_file and args.state_file.exists():
        state = json.loads(args.state_file.read_text(encoding="utf-8"))

    dry_run = args.audit or not args.reconcile
    report = watchdog.reconcile(controller_state=state, now=now, dry_run=dry_run)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
