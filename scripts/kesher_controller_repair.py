"""Bounded code-repair handoff owned by the admitted content controller.

Does not generate content, reset budgets, merge PRs, or write canonical state.
The separate CAS ledger retains unresolved incidents across daily rollover.
"""
from __future__ import annotations

import copy
import base64
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.kesher_master_supervisor_live import (
    GitHubApi, JulesRecoveryClient, SupervisorCasConflict, _pr_urls,
)

REPOSITORY = "yanivsa/kesher-website"
LEDGER_REF = "automation-supervisor-state"
LEDGER_PATH = ".kesher-controller-repair/state.json"
TERMINAL = {"verified", "human_blocker"}
JULES_TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "CANCELED"}
UNCERTAIN_LIMIT = timedelta(minutes=15)
RUNNING_LIMIT = timedelta(minutes=90)
MAX_INCIDENTS = 100


class ControllerJulesClient(JulesRecoveryClient):
    @staticmethod
    def _prompt(packet):
        return (
            "KESHER CONTROLLER CODE REPAIR. Diagnose the root cause using repository evidence, "
            "add a deterministic regression test, and propose one narrow automation-code repair PR. "
            "The content PR is evidence only: do not edit that PR, article payloads or media. "
            "Do not modify credentials, authority capabilities/topology or merge protections. "
            "Only existing reviewed hash leaves may be recertified after an existing-file correction. Do not reset budgets, "
            "generate/upload content or add recovery workflows. Reuse an existing repair PR for this incident. "
            "Include the safe continuation path for the exact affected content after reviewed deployment.\n"
            f"Put this marker in the correction PR body: <!-- kesher-controller-repair {packet.get('fingerprint', '')} -->\n"
            + json.dumps(packet, ensure_ascii=False, sort_keys=True)
        )


class RepairStore:
    def __init__(self, api):
        self.api = api

    def load(self):
        value, sha = self.api.load_state_blob(LEDGER_REF, LEDGER_PATH)
        if value is None:
            return {"version": 1, "incidents": {}}, sha
        if value.get("version") != 1 or not isinstance(value.get("incidents"), dict):
            raise ValueError("REPAIR_LEDGER_INVALID")
        return value, sha

    def save(self, state, *, expected_sha):
        return self.api.save_state_blob(LEDGER_REF, LEDGER_PATH, state, expected_sha)


class ControllerRepairAPI(GitHubApi):
    def contains_commit(self, ancestor, revision):
        if not all(re.fullmatch(r"[a-f0-9]{40}", str(s)) for s in (ancestor, revision)):
            return False
        result = self._request("GET", f"{self.api}/compare/{ancestor}...{revision}")
        return isinstance(result, dict) and result.get("status") in {"ahead", "identical"}

    def policy_hashes_only(self, number):
        pr = self.get_pr(number)
        policies = []
        for side in ("base", "head"):
            sha = str((pr.get(side) or {}).get("sha") or "")
            if not re.fullmatch(r"[a-f0-9]{40}", sha):
                return False
            blob = self._request("GET", f"{self.api}/contents/scripts/kesher_runtime/authority_policy.json?ref={sha}")
            policies.append(json.loads(base64.b64decode(blob["content"])))
        return _policy_shape(policies[0]) == _policy_shape(policies[1])


def _policy_shape(policy):
    result = copy.deepcopy(policy)
    for entry in result["workflows"].values():
        entry["definition_sha256"] = "reviewed-hash"
        review = entry["review"]
        review.pop("note", None)
        for key in review.get("call_chain", {}):
            review["call_chain"][key] = "reviewed-hash"
        for binding in review.get("dispatch_bindings", {}).values():
            binding["definition_sha256"] = "reviewed-hash"
    return result


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def diagnose(state, *, controller_failed=False):
    """Only escalate terminal failures, never normal in-flight provider work."""
    takeover = state.get("direct_takeover_required") or {}
    error = state.get("last_error") or {}
    if takeover.get("required") is True:
        stage = str(takeover.get("stage") or "controller")
        code = "DURABLE_PROGRESS_EXHAUSTED"
    elif state.get("status") == "blocked":
        stage = str(error.get("stage") or "controller")
        code = str(error.get("code") or "UNCLASSIFIED_BLOCKED_STAGE")
    elif controller_failed:
        stage, code = "controller", "CONTROLLER_WORKFLOW_FAILED"
    else:
        return None
    # Raw provider messages/logs are deliberately excluded from the task packet.
    code = re.match(r"[A-Z][A-Z0-9_]{1,100}", code)
    code = code.group() if code else "UNCLASSIFIED_BLOCKED_STAGE"
    if stage not in {"article", "image", "long_video", "short", "controller", "video"}:
        stage = "controller"
    article = state.get("article") or {}
    stage_data = state.get(stage) or {}
    exact = {key: takeover.get(key) or article.get(key) for key in
             ("slug", "content_sha256", "item_id", "task_id", "artifact_id", "source_id", "pr_number")}
    for key in ("item_id", "task_id", "artifact_id", "source_id"):
        exact[key] = takeover.get(key) or stage_data.get(key)
    exact["content_sha256"] = exact.get("content_sha256") or article.get("quality_content_sha256")
    exact["cycle"] = state["cycle"]
    exact["idea_id"] = (state.get("active_idea") or {}).get("idea_id")
    exact["article_session_id"] = (article.get("watchdog") or {}).get("session_id") or article.get("last_jules_session_id")
    exact["article_run_id"] = article.get("run_id")
    return {"stage": stage, "failure_class": code, "exact": exact}


def _delivered(state, exact):
    # A date alone cannot distinguish multiple owner ideas published that day.
    if not any(exact.get(k) for k in ("slug", "pr_number", "idea_id", "article_session_id", "article_run_id")):
        return None
    candidates = [state] + list(state.get("backlog") or [])
    for candidate in candidates:
        article = candidate.get("article") or {}
        if candidate.get("cycle") != exact["cycle"]:
            continue
        if exact.get("pr_number") and str(article.get("pr_number")) != str(exact["pr_number"]):
            continue
        if exact.get("idea_id"):
            matching = [idea for idea in state.get("idea_history", [])
                        if idea.get("idea_id") == exact["idea_id"] and idea.get("status") == "complete"
                        and (idea.get("outputs") or {}).get("slug") == article.get("slug")]
            if not matching:
                continue
        if exact.get("article_session_id"):
            known = {(article.get("watchdog") or {}).get("session_id"), article.get("last_jules_session_id")}
            if exact["article_session_id"] not in known:
                continue
        if exact.get("article_run_id") and str(article.get("run_id")) != str(exact["article_run_id"]):
            continue
        if exact.get("slug") and article.get("slug") != exact["slug"]:
            continue
        if exact.get("content_sha256") and article.get("quality_content_sha256") != exact["content_sha256"]:
            continue
        from scripts.kesher_e2e_delivery_guard import delivery_contract
        complete, urls = delivery_contract(candidate)
        if complete:
            return urls
    return None


def _correction_pr_valid(api, number, record):
    if any(str(exact.get("pr_number")) == str(number) for exact in record["affected"]):
        return False
    pr = api.get_pr(number)
    if not isinstance(pr, dict):
        return False
    base = pr.get("base") or {}
    marker = f"<!-- kesher-controller-repair {record['fingerprint']} -->"
    if (base.get("ref") != "main" or (base.get("repo") or {}).get("full_name") != REPOSITORY
            or marker not in str(pr.get("body") or "")):
        return False
    files = api.pr_files(number)
    if not files or len(files) > 12:
        return False
    policy_path = "scripts/kesher_runtime/authority_policy.json"
    if any(not p.startswith(("scripts/", "tests/")) or ".." in Path(p).parts for p in files):
        return False
    if policy_path in files and not api.policy_hashes_only(number):
        return False
    return any(p.startswith("scripts/") and p != policy_path for p in files) and any(p.startswith("tests/") for p in files)


def reconcile(state, *, store, jules, api, now=None, controller_failed=False, admit=lambda: None, deployed_revision=None):
    now = now or datetime.now(timezone.utc)
    if (not isinstance(state, dict) or type(state.get("schema_version")) is not int
            or state["schema_version"] != 5 or "handover" in state or "github_exclusion" in state):
        return {"status": "authority_refused"}
    try:
        datetime.strptime(str(state.get("cycle")), "%Y-%m-%d")
    except ValueError:
        return {"status": "authority_refused"}
    ledger, sha = store.load()
    ledger = copy.deepcopy(ledger)
    incidents = ledger["incidents"]
    observed = diagnose(state, controller_failed=controller_failed)
    current_key = None
    if observed:
        # Share one root-cause repair across affected content identities.
        current_key = _hash([observed["stage"], observed["failure_class"]])
        if current_key not in incidents:
            if len(incidents) >= MAX_INCIDENTS:
                return {"status": "human_blocker", "reason": "repair_ledger_capacity"}
            incidents[current_key] = {**observed, "status": "intent", "created_at": now.isoformat(),
                                      "fingerprint": _hash([current_key, now.isoformat()]), "affected": []}
        record = incidents[current_key]
        if observed["exact"] not in record["affected"]:
            if len(record["affected"]) >= MAX_INCIDENTS:
                return {"status": "human_blocker", "reason": "affected_identity_capacity"}
            record["affected"].append(observed["exact"])
        if record["status"] == "verified":
            record.update(status="human_blocker", reason="verified_failure_recurred")

    def persist():
        nonlocal sha
        # Re-check the durable authority immediately before every external write.
        admit()
        sha = store.save(ledger, expected_sha=sha)

    results = []
    for key, record in incidents.items():
        if record["status"] in TERMINAL:
            if key == current_key or record["status"] == "human_blocker":
                try:
                    persist()
                except SupervisorCasConflict:
                    return {"status": "cas_conflict"}
                results.append({"incident": key, "status": record["status"], "reason": record.get("reason")})
            continue
        try:
            started = datetime.fromisoformat(record["created_at"])
            age = now - started
            if record.get("pr_number"):
                pr = api.get_pr(record["pr_number"])
                if not isinstance(pr, dict):
                    raise ValueError("REPAIR_PR_UNREADABLE")
                if not _correction_pr_valid(api, record["pr_number"], record):
                    record.update(status="human_blocker", reason="repair_pr_scope_or_identity_invalid")
                elif pr.get("merged") is True and not api.contains_commit(pr.get("merge_commit_sha"), deployed_revision):
                    record["status"] = "awaiting_deployment"
                elif pr.get("merged") is True:
                    proofs = [_delivered(state, exact) for exact in record["affected"]]
                    record["status"] = "verified" if all(proofs) else "awaiting_recovery"
                    record["delivery_proofs"] = proofs
                elif pr.get("state") == "closed":
                    record.update(status="human_blocker", reason="repair_pr_closed_without_merge")
                else:
                    record["status"] = "awaiting_review"
                persist()
            elif record.get("session_id"):
                expired = now - datetime.fromisoformat(record.get("acquired_at") or record["created_at"]) >= RUNNING_LIMIT
                session = jules.get(record["session_id"]) if jules and not expired else None
                if expired:
                    record.update(status="human_blocker", reason="repair_executor_timeout")
                elif session is None:
                    record.update(status="awaiting_executor", reason="repair_executor_unavailable")
                elif str(session.get("state") or "").upper() in JULES_TERMINAL:
                    urls = _pr_urls(session)
                    pattern = rf"https://github\.com/{re.escape(REPOSITORY)}/pull/([1-9][0-9]*)"
                    matches = [re.fullmatch(pattern, url) for url in urls]
                    valid = [m for m in matches if m]
                    if len(valid) == 1 and len(urls) == 1 and _correction_pr_valid(api, int(valid[0].group(1)), record):
                        record.update(pr_number=int(valid[0].group(1)), pr_url=urls[0], status="awaiting_review")
                    else:
                        record.update(status="human_blocker", reason="repair_task_has_no_unique_repository_pr")
                else:
                    record["status"] = "running"
                persist()
            else:
                if not jules:
                    record.update(status="awaiting_executor", reason="repair_executor_credential_missing")
                    persist()
                else:
                    existing = jules.list_exact(record["fingerprint"])
                    if len(existing) == 1:
                        name = str(existing[0].get("name") or "")
                        if not name.startswith("sessions/"):
                            raise ValueError("REPAIR_SESSION_ID_INVALID")
                        record.update(session_id=name, status="running", acquired_at=record.get("acquired_at") or now.isoformat())
                        persist()
                    elif existing:
                        record.update(status="human_blocker", reason="duplicate_repair_sessions")
                        persist()
                    elif record["status"] not in {"intent", "awaiting_executor"}:
                        if now - datetime.fromisoformat(record.get("acquisition_started_at") or record["created_at"]) >= UNCERTAIN_LIMIT:
                            record.update(status="human_blocker", reason="uncertain_create_not_discoverable")
                            persist()
                    else:
                        packet = {
                            "fingerprint": record["fingerprint"], "exact": record["exact"],
                            "failure_class": record["failure_class"], "stage": record["stage"],
                            "definition_of_done": "Root-cause correction and deterministic regression test; reviewed deployment; resume the SAME affected content and verify public deliverables.",
                            "constraints": {"no_budget_reset": True, "no_new_content_or_upload": True,
                                            "no_authority_bypass": True, "no_new_workflows": True,
                                            "same_content_pr_is_evidence_not_code_repair_target": True,
                                            "scope": "automation code and tests only; no credentials, authority expansion or content mutation"},
                        }
                        # Mark uncertain BEFORE creation. A lost response or process crash
                        # can only reconcile by exact identity; never blindly create again.
                        record.update(status="uncertain", acquisition_started_at=now.isoformat())
                        persist()
                        admit()
                        name, mode = jules.acquire_or_continue(packet)
                        record.update(session_id=name, status="running", acquisition=mode, acquired_at=now.isoformat())
                        persist()
        except SupervisorCasConflict:
            return {"status": "cas_conflict", "reason": "reconcile_before_any_further_effect"}
        except Exception as exc:
            # Keep ambiguous effects unresolved and never include exception text/secrets.
            results.append({"incident": key, "status": "uncertain", "error_type": type(exc).__name__})
            continue
        results.append({"incident": key, "status": record["status"], "pr_url": record.get("pr_url"),
                        "reason": record.get("reason")})
    priority = {"human_blocker": 10, "uncertain": 9, "awaiting_executor": 8,
                "awaiting_review": 6, "awaiting_deployment": 5, "awaiting_recovery": 4, "running": 3, "verified": 0}
    return max(results, key=lambda row: priority.get(row["status"], 7)) | {"incidents": results} if results else {"status": "idle"}


def main():
    from scripts.kesher_runtime.bridge_admission import require_bridge, require_pre_cutover_controller_invocation
    from scripts.kesher_content_controller import GitHubClient
    require_pre_cutover_controller_invocation(os.environ)
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    client = GitHubClient(repo, token)
    state = client.load_controller_state()
    require_bridge(state)
    api = ControllerRepairAPI(repo, token)
    key = os.environ.get("JULES_API_KEY", "").strip()
    def admit():
        require_pre_cutover_controller_invocation(os.environ)
        require_bridge(client.load_controller_state())
    result = reconcile(state, store=RepairStore(api), jules=ControllerJulesClient(key) if key else None,
                       api=api, controller_failed=os.environ.get("KESHER_CONTROLLER_OUTCOME") == "failure", admit=admit,
                       deployed_revision=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip())
    print(json.dumps(result, sort_keys=True))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a") as handle:
            handle.write("\n### Controller repair\n\n```json\n" + json.dumps(result, indent=2) + "\n```\n")
    return 0 if result["status"] not in {"human_blocker", "authority_refused", "uncertain", "awaiting_executor"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
