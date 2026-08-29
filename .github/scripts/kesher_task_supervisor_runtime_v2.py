#!/usr/bin/env python3
"""Final runtime patch: explicit deploy after a GITHUB_TOKEN merge.

GitHub deliberately suppresses normal push-triggered workflow recursion for
changes made with the repository GITHUB_TOKEN. The supervisor therefore uses
workflow_dispatch exactly once after its own merge, then verifies that exact
run against the captured main SHA before live validation.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

RUNTIME_PATH = pathlib.Path(__file__).with_name("kesher_task_supervisor_runtime.py")
spec = importlib.util.spec_from_file_location("kesher_task_supervisor_runtime_impl", RUNTIME_PATH)
runtime = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = runtime
spec.loader.exec_module(runtime)

base = runtime.base
EXPECTED_DEPLOY_SHA = ""


def select_supervisor_deploy(
    runs: list[dict[str, Any]], expected_sha: str, after: datetime
) -> dict[str, Any] | None:
    for run in runs:
        if str(run.get("event") or "") != "workflow_dispatch":
            continue
        if str(run.get("head_sha") or "") != expected_sha:
            continue
        if base.parse_time(str(run.get("created_at") or "")) < after:
            continue
        return run
    return None


def dispatch_supervisor_deploy() -> datetime | None:
    global EXPECTED_DEPLOY_SHA
    if base.DRY_RUN:
        base.meaningful_changes.append("DRY-RUN: would dispatch one deploy.yml workflow_dispatch")
        return None

    EXPECTED_DEPLOY_SHA = runtime.current_main_sha()
    started = datetime.now(timezone.utc) - timedelta(seconds=5)
    status, _ = base.gh(
        "POST",
        f"/repos/{base.REPO}/actions/workflows/deploy.yml/dispatches",
        {"ref": "main"},
        allow={204},
    )
    if status != 204:
        raise base.ApiError(f"deploy workflow_dispatch returned {status}")
    base.meaningful_changes.append(
        f"Dispatched one deploy.yml run for merged main {EXPECTED_DEPLOY_SHA[:12]}"
    )
    return started


def wait_for_supervisor_deploy(after: datetime | None) -> base.GateState:
    if after is None:
        return base.GateState("pending", "dry-run deploy")
    expected_sha = EXPECTED_DEPLOY_SHA
    if not expected_sha:
        return base.GateState("failed", "missing captured main SHA for deploy verification")

    deadline = time.monotonic() + base.DEPLOY_WAIT_SECONDS
    last_seen = "none"
    while time.monotonic() < deadline:
        _, data = base.gh(
            "GET",
            f"/repos/{base.REPO}/actions/workflows/deploy.yml/runs?branch=main&event=workflow_dispatch&per_page=20",
        )
        run = select_supervisor_deploy(data.get("workflow_runs") or [], expected_sha, after)
        if run:
            last_seen = str(run.get("id") or "unknown")
            status = str(run.get("status") or "")
            conclusion = str(run.get("conclusion") or "")
            if status == "completed":
                if conclusion == "success":
                    return base.GateState(
                        "green",
                        f"supervisor deploy run {last_seen} succeeded for main {expected_sha[:12]}",
                    )
                return base.GateState(
                    "failed",
                    f"supervisor deploy run {last_seen} concluded {conclusion} for main {expected_sha[:12]}",
                )
        time.sleep(base.DEPLOY_POLL_SECONDS)

    return base.GateState(
        "pending",
        f"supervisor deploy run {last_seen} for main {expected_sha[:12]} did not finish within controller window",
    )


# Override the intermediate runtime's push-observation policy. This explicit
# dispatch is safe because workflow_dispatch is the documented recursion-safe
# way to trigger a workflow from another workflow using GITHUB_TOKEN.
base.dispatch_deploy = dispatch_supervisor_deploy
base.wait_for_deploy = wait_for_supervisor_deploy


if __name__ == "__main__":
    raise SystemExit(base.main())
