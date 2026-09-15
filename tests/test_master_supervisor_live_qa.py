from __future__ import annotations

import unittest
from unittest import mock

from scripts import kesher_master_supervisor_live as live


def incident_report() -> dict:
    return {
        "mode": "live",
        "status": "incident_detected",
        "incident_id": "v5|slug-a|hash-a|long_video",
        "failure_signature": "OVERVIEW_SIGNATURE_FULLSCREEN_MISSING",
        "evidence_hash": "evidence-a",
        "proposed_action": "rebuild_exact_overview",
        "exact": {
            "slug": "slug-a",
            "content_sha256": "hash-a",
            "item_id": "video-1",
        },
    }


class FakePrApi:
    def __init__(self) -> None:
        self.merged = False
        self.dispatched: list[tuple[str, dict | None]] = []

    def get_pr(self, number: int):
        return {
            "number": number,
            "state": "open",
            "draft": False,
            "mergeable": True,
            "head": {"sha": "head-123"},
        }

    def pr_files(self, number: int):
        return ["scripts/fix.py", "tests/test_fix.py"]

    def combined_status(self, sha: str):
        return {"statuses": []}

    def check_runs(self, sha: str):
        return [{"name": "verify", "status": "completed", "conclusion": "success"}]

    def merge_pr(self, number: int, sha: str):
        self.merged = True
        return {"merged": True, "sha": "merge-123"}

    def dispatch_workflow(self, workflow: str, inputs: dict | None = None):
        self.dispatched.append((workflow, inputs))


class FakeAdoptedRunApi:
    def active_external_media_run(self):
        return None

    def workflow_run_by_id(self, run_id):
        self.seen_run_id = run_id
        return {"id": run_id, "status": "completed", "conclusion": "success"}


class MasterSupervisorLiveQaTests(unittest.TestCase):
    def test_healthy_exact_source_resolves_prior_active_incident(self) -> None:
        report = incident_report()
        state, decision = live.prepare_escalation(
            live.new_supervisor_state(),
            report,
            now="2026-09-16T00:00:00+00:00",
            prior_action_terminal=False,
        )
        state = live.mark_command_acknowledged(
            state,
            decision["command_id"],
            {"workflow": "kesher-content-controller.yml"},
            at="2026-09-16T00:00:05+00:00",
        )
        healthy = {
            "mode": "live",
            "status": "healthy_or_in_flight",
            "incident_id": None,
            "failure_signature": None,
            "exact": {"slug": "slug-a", "content_sha256": "hash-a"},
        }
        updated, changed = live.resolve_absent_incidents(
            state,
            healthy,
            at="2026-09-16T00:05:00+00:00",
        )
        fp = live.incident_fingerprint(report)
        self.assertTrue(changed)
        self.assertEqual(updated["incidents"][fp]["status"], "resolved")
        self.assertEqual(updated["commands"][decision["command_id"]]["lifecycle"], "verified")

    def test_waiting_for_authoritative_article_does_not_close_prior_incidents(self) -> None:
        report = incident_report()
        state, decision = live.prepare_escalation(
            live.new_supervisor_state(),
            report,
            now="2026-09-16T00:00:00+00:00",
            prior_action_terminal=False,
        )
        waiting = {
            "mode": "live",
            "status": "waiting_for_authoritative_article",
            "incident_id": None,
            "failure_signature": None,
            "exact": {},
        }
        updated, changed = live.resolve_absent_incidents(state, waiting, at="2026-09-16T00:05:00+00:00")
        self.assertFalse(changed)
        self.assertEqual(updated["commands"][decision["command_id"]]["lifecycle"], "issued")

    def test_jules_exact_session_lookup_paginates_before_creating_anything(self) -> None:
        calls: list[str] = []

        def fake_request(method, url, headers, *args, **kwargs):
            calls.append(url)
            if "pageToken=next-1" in url:
                return {
                    "sessions": [{"name": "sessions/existing", "title": "Kesher recovery fp-1", "state": "IN_PROGRESS"}],
                }
            return {
                "sessions": [{"name": "sessions/other", "title": "Other task", "state": "COMPLETED"}],
                "nextPageToken": "next-1",
            }

        client = live.JulesRecoveryClient("test-key")
        with mock.patch.object(live.jules, "request_json", side_effect=fake_request):
            rows = client.list_exact("fp-1")
        self.assertEqual([row["name"] for row in rows], ["sessions/existing"])
        self.assertEqual(len(calls), 2)
        self.assertIn("pageToken=next-1", calls[1])

    def test_multiple_exact_jules_sessions_fail_closed(self) -> None:
        client = live.JulesRecoveryClient("test-key")
        with mock.patch.object(
            client,
            "list_exact",
            return_value=[
                {"name": "sessions/one", "title": client.title("fp-1"), "state": "IN_PROGRESS"},
                {"name": "sessions/two", "title": client.title("fp-1"), "state": "IN_PROGRESS"},
            ],
        ):
            with self.assertRaises(live.SupervisorError):
                client.acquire_or_continue({"fingerprint": "fp-1", "incident_id": "i", "failure_signature": "f", "exact": {}, "definition_of_done": "d", "constraints": {}})

    def test_s1_adopted_preexisting_controller_run_reconciles_by_run_id(self) -> None:
        report = incident_report()
        state, s1 = live.prepare_escalation(
            live.new_supervisor_state(),
            report,
            now="2026-09-16T00:00:00+00:00",
            prior_action_terminal=False,
        )
        state = live.mark_command_acknowledged(
            state,
            s1["command_id"],
            {"workflow": "kesher-content-controller.yml", "dispatch": "already_active", "run_id": 55},
            at="2026-09-16T00:00:01+00:00",
        )
        api = FakeAdoptedRunApi()
        updated, terminal, reason = live.reconcile_active_command(
            state,
            report,
            api=api,
            jules_client=None,
            now="2026-09-16T00:05:00+00:00",
        )
        self.assertEqual(api.seen_run_id, 55)
        self.assertTrue(terminal)
        self.assertEqual(reason, "workflow_completed_incident_persisted")
        self.assertEqual(updated["commands"][s1["command_id"]]["lifecycle"], "failed")

    def test_s3_recovery_pr_accepts_required_verify_check_run_not_only_legacy_status(self) -> None:
        api = FakePrApi()
        result = live.try_finalize_recovery_pr(api, 900)
        self.assertEqual(result, {"recovery_pr_number": 900, "merge_sha": "merge-123"})
        self.assertTrue(api.merged)

    def test_s3_recovery_pr_merge_explicitly_wakes_controller(self) -> None:
        api = FakePrApi()
        report = incident_report()
        state, s1 = live.prepare_escalation(live.new_supervisor_state(), report, now="2026-09-16T00:00:00+00:00", prior_action_terminal=False)
        state = live.mark_command_failed(state, s1["command_id"], "failed", at="2026-09-16T00:01:00+00:00")
        state, s2 = live.prepare_escalation(state, report, now="2026-09-16T00:01:01+00:00", prior_action_terminal=True)
        state["commands"][s2["command_id"]].setdefault("metadata", {})["recovery_pr_number"] = 900
        state = live.mark_command_failed(state, s2["command_id"], "jules complete", at="2026-09-16T00:02:00+00:00")
        state, s3 = live.prepare_escalation(state, report, now="2026-09-16T00:02:01+00:00", prior_action_terminal=True)
        updated = live.execute_command(
            state,
            report,
            s3,
            api=api,
            jules_client=None,
            now="2026-09-16T00:02:02+00:00",
        )
        self.assertTrue(api.merged)
        self.assertIn(("kesher-content-controller.yml", None), api.dispatched)
        self.assertEqual(updated["commands"][s3["command_id"]]["metadata"]["workflow"], "recovery_pr_merge")
        self.assertTrue(updated["commands"][s3["command_id"]]["metadata"]["controller_dispatched_after_merge"])

    def test_jules_incident_packet_never_tells_agent_to_regenerate_media(self) -> None:
        packet = live.build_incident_packet(incident_report(), strike=2, command_id="ksr-qa")
        self.assertTrue(packet["constraints"]["no_duplicate_generation_upload"])
        self.assertTrue(packet["constraints"]["reuse_existing_session_pr"])
        self.assertEqual(packet["exact"]["item_id"], "video-1")


if __name__ == "__main__":
    unittest.main()
