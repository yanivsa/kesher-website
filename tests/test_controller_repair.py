from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone

from scripts import kesher_controller_repair as repair


NOW = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)


def blocked():
    return {"schema_version": 5, "cycle": "2026-10-29", "status": "blocked",
            "article": {"status": "exhausted", "pr_number": 1249},
            "last_error": {"stage": "article", "code": "ARTICLE_STAGE_BUDGET_EXHAUSTED",
                           "message": "must never copy arbitrary provider text into repair prompt"}}


class Store:
    def __init__(self):
        self.value = {"version": 1, "incidents": {}}
        self.saves = 0

    def load(self):
        return copy.deepcopy(self.value), str(self.saves)

    def save(self, state, *, expected_sha):
        if expected_sha != str(self.saves):
            raise repair.SupervisorCasConflict("stale")
        self.value = copy.deepcopy(state)
        self.saves += 1
        return str(self.saves)


class Jules:
    def __init__(self, store):
        self.store = store
        self.sessions = []
        self.creates = []
        self.uncertain = False
        self.state = "IN_PROGRESS"
        self.urls = []

    def list_exact(self, fingerprint):
        return copy.deepcopy(self.sessions)

    def acquire_or_continue(self, packet):
        # The intent must be durable before creation, even if its response is lost.
        assert any(r["status"] == "uncertain" for r in self.store.value["incidents"].values())
        self.creates.append(packet)
        self.sessions = [{"name": "sessions/repair-1"}]
        if self.uncertain:
            raise TimeoutError("lost create acknowledgement")
        return "sessions/repair-1", "created"

    def get(self, session_id):
        return {"state": self.state, "outputs": [{"pullRequest": {"url": u}} for u in self.urls]}


class API:
    def __init__(self, store):
        self.store = store
        self.merged = False
        self.base = "main"
        self.deployed = True
    def get_pr(self, number):
        fp = next(iter(self.store.value["incidents"].values()))["fingerprint"]
        return {"number": number, "merged": self.merged, "state": "open",
                "merge_commit_sha": "merge-fix", "body": f"<!-- kesher-controller-repair {fp} -->",
                "base": {"ref": self.base, "repo": {"full_name": repair.REPOSITORY}}}
    def pr_files(self, number):
        return ["scripts/kesher_controller_repair.py", "tests/test_controller_repair.py"]
    def contains_commit(self, ancestor, revision):
        return self.deployed


class ControllerRepairTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.jules = Jules(self.store)
        self.api = API(self.store)

    def run_repair(self, state=None, now=NOW, **kwargs):
        return repair.reconcile(state or blocked(), store=self.store, jules=self.jules,
                                api=self.api, now=now, deployed_revision="current-revision", **kwargs)

    def test_exhaustion_before_article_creates_one_repair_and_persists_intent(self):
        first = self.run_repair()
        second = self.run_repair(now=NOW + timedelta(minutes=5))
        self.assertEqual(first["status"], "running")
        self.assertEqual(second["status"], "running")
        self.assertEqual(len(self.jules.creates), 1)
        packet = self.jules.creates[0]
        self.assertEqual(packet["exact"]["pr_number"], 1249)
        self.assertIn("deterministic regression", packet["definition_of_done"])
        self.assertNotIn("arbitrary provider text", str(packet))

    def test_lost_create_response_reconciles_existing_task_without_recreation(self):
        self.jules.uncertain = True
        self.assertEqual(self.run_repair()["status"], "uncertain")
        self.assertEqual(self.run_repair(now=NOW + timedelta(minutes=5))["status"], "running")
        self.assertEqual(len(self.jules.creates), 1)

    def test_uncertain_absent_session_is_never_blindly_recreated(self):
        self.jules.uncertain = True
        self.run_repair()
        self.jules.sessions = []
        result = self.run_repair(now=NOW + timedelta(minutes=16))
        self.assertEqual(result["status"], "human_blocker")
        self.assertEqual(len(self.jules.creates), 1)

    def test_running_task_has_absolute_timeout(self):
        self.run_repair()
        result = self.run_repair(now=NOW + timedelta(minutes=91))
        self.assertEqual(result["status"], "human_blocker")
        self.assertEqual(len(self.jules.creates), 1)

    def test_unreachable_executor_cannot_extend_runtime_forever(self):
        self.run_repair()
        def unavailable(session_id):
            raise TimeoutError("provider unreachable")
        self.jules.get = unavailable
        self.assertEqual(self.run_repair(now=NOW + timedelta(minutes=91))["status"], "human_blocker")

    def test_direct_takeover_is_actionable_even_without_blocked_status(self):
        state = blocked()
        state.update(status="long_video_running", last_error=None,
                     direct_takeover_required={"required": True, "stage": "long_video",
                                               "slug": "topic", "content_sha256": "a" * 64,
                                               "item_id": "existing-video", "task_id": "provider-task"})
        self.assertEqual(self.run_repair(state)["status"], "running")
        self.assertEqual(self.jules.creates[0]["exact"]["item_id"], "existing-video")

    def test_handover_refuses_even_a_pending_repair(self):
        self.run_repair()
        for change in ({"schema_version": 6}, {"handover": {}}, {"github_exclusion": {}}):
            state = blocked() | change
            self.assertEqual(self.run_repair(state)["status"], "authority_refused")
        self.assertEqual(len(self.jules.creates), 1)

    def test_jules_completed_pr_is_not_repair_success(self):
        self.run_repair()
        self.jules.state = "COMPLETED"
        self.jules.urls = ["https://github.com/yanivsa/kesher-website/pull/1250"]
        self.assertEqual(self.run_repair()["status"], "awaiting_review")
        self.api.merged = True
        self.assertEqual(self.run_repair()["status"], "awaiting_recovery")

    def test_unrelated_complete_cycle_does_not_close_old_repair(self):
        self.run_repair()
        state = blocked() | {"cycle": "2026-10-30", "status": "complete", "last_error": None,
                             "deliverables": {"article_url": "other", "overview_youtube_url": "other", "short_youtube_url": "other"}}
        self.run_repair(state)
        incident = next(iter(self.store.value["incidents"].values()))
        self.assertNotEqual(incident["status"], "verified")
        self.assertEqual(len(self.jules.creates), 1)

    def test_healthy_cycle_never_creates_repair(self):
        result = self.run_repair(blocked() | {"status": "complete", "last_error": None})
        self.assertEqual(result["status"], "idle")
        self.assertFalse(self.jules.creates)

    def test_missing_executor_can_resume_after_credential_is_restored(self):
        result = repair.reconcile(blocked(), store=self.store, jules=None, api=self.api, now=NOW)
        self.assertEqual(result["status"], "awaiting_executor")
        self.assertEqual(self.run_repair()["status"], "running")

    def test_time_waiting_for_credentials_does_not_consume_task_runtime(self):
        repair.reconcile(blocked(), store=self.store, jules=None, api=self.api, now=NOW)
        self.run_repair(now=NOW + timedelta(hours=2))
        self.assertEqual(self.run_repair(now=NOW + timedelta(hours=2, minutes=5))["status"], "running")

    def test_content_pr_cannot_masquerade_as_correction(self):
        self.run_repair()
        self.jules.state = "COMPLETED"
        self.jules.urls = ["https://github.com/yanivsa/kesher-website/pull/1249"]
        self.assertEqual(self.run_repair()["status"], "human_blocker")

    def test_wrong_base_pr_is_rejected(self):
        self.run_repair()
        self.jules.state = "COMPLETED"
        self.jules.urls = ["https://github.com/yanivsa/kesher-website/pull/1250"]
        self.api.base = "other"
        self.assertEqual(self.run_repair()["status"], "human_blocker")

    def test_authority_change_before_external_creation_prevents_task(self):
        calls = []
        def admit():
            calls.append(True)
            if len(calls) == 2:
                raise RuntimeError("handover started")
        self.run_repair(admit=admit)
        self.assertFalse(self.jules.creates)

    def test_content_identity_is_not_taken_from_another_stage(self):
        state = blocked()
        state["last_error"]["stage"] = "long_video"
        state["long_video"] = {"item_id": "existing-overview", "task_id": "provider-existing"}
        self.run_repair(state)
        self.assertEqual(self.jules.creates[0]["exact"]["item_id"], "existing-overview")

    def test_terminal_recurrence_is_saved_without_creating_second_task(self):
        self.run_repair()
        record = next(iter(self.store.value["incidents"].values()))
        record["status"] = "verified"
        self.run_repair()
        self.assertEqual(next(iter(self.store.value["incidents"].values()))["status"], "human_blocker")
        self.assertEqual(len(self.jules.creates), 1)

    def test_repair_prompt_does_not_target_the_content_pr(self):
        prompt = repair.ControllerJulesClient._prompt({"exact": {"pr_number": 1249}})
        self.assertIn("content PR is evidence only", prompt)

    def test_real_delivery_contract_closes_only_after_merged_correction(self):
        from tests.test_kesher_recovery_e2e import sample_source, make_valid_long_item, make_valid_short_item
        source = sample_source(day="2026-10-29")
        overview = make_valid_long_item(source)
        overview.update(signature_fullscreen=True)
        # Use the real production contract; its technical/signature evidence is
        # the same proven fixture used by the repository's recovery suite.
        from scripts.kesher_e2e_delivery_guard import delivery_contract
        state = blocked()
        self.run_repair(state)
        self.jules.state = "COMPLETED"
        self.jules.urls = ["https://github.com/yanivsa/kesher-website/pull/1250"]
        self.run_repair(state)
        state.update(status="complete", last_error=None,
                     article={"pr_number": 1249, "url": "https://kesher.saharoni.com/blog/topic", "live": True},
                     long_video=overview, short=make_valid_short_item(source, overview))
        ready, _ = delivery_contract(state)
        self.assertTrue(ready)
        self.assertEqual(self.run_repair(state)["status"], "awaiting_review")
        self.api.merged = True
        state["short"]["signature_verified"] = False
        self.assertEqual(self.run_repair(state)["status"], "awaiting_recovery")
        state["short"]["signature_verified"] = True
        self.assertEqual(self.run_repair(state)["status"], "verified")
        self.assertEqual(len(self.jules.creates), 1)

    def test_controller_crash_without_error_is_diagnosed(self):
        state = blocked() | {"status": "article_generating", "last_error": None}
        result = self.run_repair(state, controller_failed=True)
        self.assertEqual(result["status"], "running")

    def test_historical_human_blocker_remains_visible_after_rollover(self):
        self.run_repair()
        next(iter(self.store.value["incidents"].values()))["status"] = "human_blocker"
        result = self.run_repair(blocked() | {"cycle": "2026-10-30", "status": "complete", "last_error": None})
        self.assertEqual(result["status"], "human_blocker")

    def test_later_blocker_is_not_masked_by_earlier_running_incident(self):
        self.run_repair()
        row = copy.deepcopy(next(iter(self.store.value["incidents"].values())))
        row["status"] = "human_blocker"
        self.store.value["incidents"]["later-blocker"] = row
        self.assertEqual(self.run_repair()["status"], "human_blocker")

    def test_prepublication_owner_identity_is_retained_for_later_verification(self):
        state = blocked()
        state["article"] = {"status": "exhausted"}
        state["active_idea"] = {"idea_id": "owner-idea-1"}
        self.run_repair(state)
        exact = next(iter(self.store.value["incidents"].values()))["exact"]
        self.assertEqual(exact["idea_id"], "owner-idea-1")

    def test_owner_identity_matures_into_exact_public_delivery(self):
        from tests.test_kesher_recovery_e2e import sample_source, make_valid_long_item, make_valid_short_item
        state = blocked() | {"article": {"run_id": 111}, "active_idea": {"idea_id": "owner-idea-1"}}
        self.run_repair(state)
        self.jules.state = "COMPLETED"
        self.jules.urls = ["https://github.com/yanivsa/kesher-website/pull/1250"]
        self.run_repair(state)
        source = sample_source(day="2026-10-29")
        overview = make_valid_long_item(source) | {"signature_fullscreen": True}
        state.update(status="complete", last_error=None, active_idea=None,
                     idea_history=[{"idea_id": "owner-idea-1", "status": "complete", "outputs": {"slug": source["slug"]}}],
                     article={"run_id": 222, "slug": source["slug"], "url": "https://kesher.saharoni.com/blog/" + source["slug"], "live": True},
                     long_video=overview, short=make_valid_short_item(source, overview))
        self.api.merged = True
        self.api.deployed = False
        self.assertEqual(self.run_repair(state)["status"], "awaiting_deployment")
        self.api.deployed = True
        self.assertEqual(self.run_repair(state)["status"], "verified")

    def test_lost_ledger_acknowledgement_after_creation_does_not_duplicate_task(self):
        save = self.store.save
        def lost_ack(value, *, expected_sha):
            if any(r.get("session_id") for r in value["incidents"].values()):
                raise TimeoutError("ack lost")
            return save(value, expected_sha=expected_sha)
        self.store.save = lost_ack
        self.assertEqual(self.run_repair()["status"], "uncertain")
        self.store.save = save
        self.assertEqual(self.run_repair()["status"], "running")
        self.assertEqual(len(self.jules.creates), 1)

    def test_cas_conflict_before_creation_has_no_external_effect(self):
        def conflict(*args, **kwargs):
            raise repair.SupervisorCasConflict("concurrent change")
        self.store.save = conflict
        self.assertEqual(self.run_repair()["status"], "cas_conflict")
        self.assertFalse(self.jules.creates)

    def test_policy_recertification_preserves_capabilities_and_reviewed_paths(self):
        policy = {"workflows": {"controller": {"definition_sha256": "a", "capabilities": ["read"],
                  "review": {"call_chain": {"scripts/existing.py": "a"}, "dispatch_bindings": {}}}}}
        refreshed = copy.deepcopy(policy)
        refreshed["workflows"]["controller"]["definition_sha256"] = "b"
        refreshed["workflows"]["controller"]["review"]["call_chain"]["scripts/existing.py"] = "b"
        self.assertEqual(repair._policy_shape(policy), repair._policy_shape(refreshed))
        refreshed["workflows"]["controller"]["capabilities"].append("merge")
        self.assertNotEqual(repair._policy_shape(policy), repair._policy_shape(refreshed))
        refreshed = copy.deepcopy(policy)
        refreshed["workflows"]["controller"]["review"]["call_chain"]["scripts/new.py"] = "b"
        self.assertNotEqual(repair._policy_shape(policy), repair._policy_shape(refreshed))

    def test_actual_policy_recertification_transport_binds_base_and_head(self):
        import base64, json
        api = repair.ControllerRepairAPI(repair.REPOSITORY, "test-token")
        policy = {"workflows": {"controller": {"definition_sha256": "a", "review": {"call_chain": {}, "dispatch_bindings": {}}}}}
        seen = []
        def request(method, url):
            seen.append(url)
            return {"content": base64.b64encode(json.dumps(policy).encode()).decode()}
        api._request = request
        api.get_pr = lambda number: {"base": {"sha": "a" * 40}, "head": {"sha": "b" * 40}}
        self.assertTrue(api.policy_hashes_only(1250))
        self.assertTrue(seen[0].endswith("ref=" + "a" * 40))
        self.assertTrue(seen[1].endswith("ref=" + "b" * 40))

    def test_daily_cron_has_target_minute_for_both_israel_offsets(self):
        from pathlib import Path
        import yaml
        path = Path(__file__).resolve().parents[1] / ".github/workflows/kesher-content-controller.yml"
        data = yaml.safe_load(path.read_text())
        crons = [s["cron"] for s in data.get("on", data.get(True))["schedule"]]
        self.assertIn("35 21,22 * * *", crons)

    def test_workflow_invokes_coordinator_after_controller_failure(self):
        from pathlib import Path
        import yaml
        path = Path(__file__).resolve().parents[1] / ".github/workflows/kesher-content-controller.yml"
        steps = yaml.safe_load(path.read_text())["jobs"]["control"]["steps"]
        coordinator = next(s for s in steps if "scripts.kesher_controller_repair" in s.get("run", ""))
        self.assertIn("always()", coordinator["if"])
        self.assertIn("bridge_admission.outcome == 'success'", coordinator["if"])


if __name__ == "__main__":
    unittest.main()
