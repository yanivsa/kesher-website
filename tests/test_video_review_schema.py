from __future__ import annotations

# Runtime contract regression suite for the strict advisory Jules review.
import importlib.util
import copy
import json
import hashlib
import os
import tempfile
import sys
import types
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEWER_PATH = ROOT / "scripts" / "jules_video_reviewer_v3.py"
POLICY_PATH = ROOT / ".github" / "prompts" / "jules-remotion-video-upgrade.md"


def load_reviewer(frame_count: int = 8):
    previous = sys.modules.get("kesher_daily_pipeline")
    stub = types.ModuleType("kesher_daily_pipeline")
    stub.REVIEW_FRAME_COUNT = frame_count
    sys.modules["kesher_daily_pipeline"] = stub
    try:
        spec = importlib.util.spec_from_file_location("jules_video_reviewer_schema_test", REVIEWER_PATH)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.REVIEW_FRAME_COUNT = frame_count
        return module
    finally:
        if previous is None:
            sys.modules.pop("kesher_daily_pipeline", None)
        else:
            sys.modules["kesher_daily_pipeline"] = previous


def approved_decision(reviewer):
    decision = reviewer.review_json_example("item-1")
    decision.update(
        {
            "schema_version": reviewer.REVIEW_SCHEMA_VERSION,
            "policy_version": reviewer.REMOTION_POLICY_VERSION,
            "decision": "approved",
            "blocking_issues": [],
            "recommendations": [],
            "visual_status": "approved",
            "semantic_status": "approved",
            "metadata_status": "approved",
            "visual_note": "כל הפריימים מציגים רצף חזותי טבעי ומבוסס מקור ללא השתלטות גרפית",
            "semantic_note": "התמלול והווידאו משמרים במדויק את הנושא המרכזי של מאמר המקור",
            "metadata_note": "הכותרת התיאור והתגיות תואמים למאמר ונשארים בעברית טבעית",
        }
    )
    return decision


class VideoReviewSchemaTests(unittest.TestCase):
    def _schema_repair_case(self, *, change_quality=False, wrong_hash=False):
        adapter = load_reviewer()
        reviewer = adapter.legacy
        valid = approved_decision(adapter)
        hashes = {key: 'a' * 64 for key in ('manifest_sha256', 'final_sha256', 'transcript_sha256', 'source_file_sha256', 'visual_review_sha256')}
        hashes['frame_sha256'] = {f'frame-{i:02d}.jpg': 'a' * 64 for i in range(1, 9)}
        valid.update(hashes)
        valid.update(decision='rejected', visual_status='rejected', blocking_issues=[{'gate': 'visual', 'code': 'REPEATED_FRAMES', 'message': 'הפריימים חוזרים על עצמם ואינם מציגים התקדמות חזותית'}])
        invalid = copy.deepcopy(valid)
        invalid['blocking_issues'][0]['gate'] = 'unknown-gate'
        if wrong_hash:
            invalid['manifest_sha256'] = 'b' * 64
        if change_quality:
            valid.update(decision='approved', visual_status='approved', blocking_issues=[])
        messages = [f'{reviewer.FINAL_MARKER}\n' + json.dumps(d, ensure_ascii=False) for d in (invalid, valid)]
        posts = []
        def request(method, path, key, body=None):
            if method == 'POST':
                posts.append((path, body))
                return {}
            return {'state': 'COMPLETED'}
        with mock.patch.object(reviewer, 'create_session', return_value='sessions/exact') as create, mock.patch.object(reviewer, 'request_json', side_effect=request), mock.patch.object(reviewer, 'list_activities', side_effect=[[{'agentMessaged': {'agentMessage': messages[0]}}], [{'agentMessaged': {'agentMessage': msg}} for msg in messages]]), mock.patch.object(reviewer.time, 'sleep'), mock.patch.object(reviewer, 'STRUCTURED_OUTPUT_REPAIR_GRACE_SECONDS', 0):
            if change_quality or wrong_hash:
                error = 'quality decision' if change_quality else 'evidence mismatch'
                with self.assertRaisesRegex(reviewer.ReviewError, error):
                    reviewer.obtain_validated_decision('key', 'prompt', {'id': 'item-1'}, hashes, 'branch', 30)
                if wrong_hash:
                    self.assertEqual(posts, [])
            else:
                decision, session = reviewer.obtain_validated_decision('key', 'prompt', {'id': 'item-1'}, hashes, 'branch', 30)
                self.assertEqual(decision, valid)
                self.assertEqual(session, 'sessions/exact')
                self.assertEqual(len(posts), 1)
                self.assertEqual(posts[0][0], '/sessions/exact:sendMessage')
                create.assert_called_once()

    def test_schema_invalid_gate_is_corrected_in_same_session_without_changing_rejection(self):
        self._schema_repair_case()

    def test_schema_repair_cannot_turn_rejection_into_approval(self):
        self._schema_repair_case(change_quality=True)

    def test_wrong_evidence_hash_is_not_treated_as_schema_repair(self):
        self._schema_repair_case(wrong_hash=True)

    def test_schema_correction_is_bounded_in_one_session(self):
        adapter = load_reviewer()
        reviewer = adapter.legacy
        decision = approved_decision(adapter)
        decision.update(decision='rejected', visual_status='rejected', blocking_issues=[{'gate': 'unknown', 'code': 'BAD_GATE', 'message': 'הפריימים חוזרים על עצמם ללא התקדמות חזותית'}])
        message = reviewer.FINAL_MARKER + '\n' + json.dumps(decision, ensure_ascii=False)
        posts = []
        def request(method, path, key, body=None):
            if method == 'POST': posts.append(path)
            return {'state': 'COMPLETED'}
        with mock.patch.object(reviewer, 'request_json', side_effect=request), mock.patch.object(reviewer, 'list_activities', return_value=[{'agentMessaged': {'agentMessage': message}}]), mock.patch.object(reviewer.time, 'sleep'), mock.patch.object(reviewer, 'STRUCTURED_OUTPUT_REPAIR_GRACE_SECONDS', 0):
            with self.assertRaisesRegex(reviewer.ReviewError, 'invalid gate'):
                reviewer.wait_for_message('key', 'sessions/same', 30, decision_validator=reviewer.validate_structured_contract)
        self.assertEqual(posts, ['/sessions/same:sendMessage', '/sessions/same:sendMessage'])

    def _advisory_state_fixture(self, root):
        adapter = load_reviewer()
        item = {'id': 'video-20261026-131504-d4ece4f847-a2', 'type': 'video_overview', 'status': 'pending_review', 'fresh_generation_attempt': 2, 'source': {'slug': 'test-article', 'content_sha256': 'a' * 64}, 'frame_paths': [], 'frame_sha256': {}}
        for index in range(1, 9):
            name = f'frame-{index}.jpg';data = f'frame {index}'.encode();(root/name).write_bytes(data)
            item['frame_paths'].append(name);item['frame_sha256'][name] = hashlib.sha256(data).hexdigest()
        for key in ['manifest_sha256', 'final_sha256', 'transcript_sha256', 'source_file_sha256', 'visual_review_sha256']:
            item[key] = 'b' * 64
        state = {'version': 1, 'items': [item]};(root/'state.json').write_text(json.dumps(state))
        decision = approved_decision(adapter);decision['item_id'] = item['id']
        decision.update(adapter.legacy.expected_hashes(root, item))
        return adapter, item, decision

    def test_advisory_records_quality_without_calling_retired_publication_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);adapter,item,decision = self._advisory_state_fixture(root)
            args = ['review', '--state-dir', str(root), '--target-slug', 'test-article', '--target-content-sha256', 'a' * 64, '--item-id', item['id'], '--review-branch', 'kesher-video-review-123', '--evidence-root', 'evidence']
            with mock.patch('sys.argv', args), mock.patch.dict(os.environ, {'JULES_API_KEY': 'test-key'}), mock.patch.object(adapter.legacy, 'obtain_validated_decision', return_value=(decision, 'sessions/123')), mock.patch.object(adapter.legacy.subprocess, 'run', side_effect=AssertionError('retired publication path must not be invoked')):
                self.assertEqual(adapter.main(), 0)
            recorded = json.loads((root/'state.json').read_text())['items'][0]
            self.assertEqual(recorded['status'], 'pending_review')
            self.assertEqual(recorded['jules_advisory_review']['decision'], decision)
            self.assertEqual({k:v for k,v in recorded.items() if k != 'jules_advisory_review'}, item)

    def test_advisory_rejection_is_persisted_idempotently_without_publication_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);adapter,item,decision = self._advisory_state_fixture(root)
            decision.update(decision='rejected', visual_status='rejected', blocking_issues=[{'gate':'visual','code':'REPEATED_FRAMES','message':'הפריימים חוזרים על עצמם ללא התפתחות חזותית'}])
            with mock.patch.dict(os.environ, {'TARGET_SLUG': 'test-article', 'TARGET_CONTENT_SHA256': 'a' * 64}):
                adapter.record_advisory_decision(root, decision, 'sessions/123', copy.deepcopy(item))
                first = (root/'state.json').read_bytes()
                adapter.record_advisory_decision(root, decision, 'sessions/123', copy.deepcopy(item))
            self.assertEqual((root/'state.json').read_bytes(), first)
            result = json.loads(first)['items'][0]
            self.assertFalse(result['jules_advisory_review']['publication_authority'])
            self.assertEqual(result['jules_advisory_review']['decision']['decision'], 'rejected')
            self.assertEqual({k:v for k,v in result.items() if k != 'jules_advisory_review'}, item)

    def test_advisory_evidence_mismatch_refuses_record_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);adapter,item,decision = self._advisory_state_fixture(root)
            decision['final_sha256'] = 'c' * 64
            original = (root/'state.json').read_bytes()
            with mock.patch.dict(os.environ, {'TARGET_SLUG': 'test-article', 'TARGET_CONTENT_SHA256': 'a' * 64}), self.assertRaisesRegex(adapter.ReviewError, 'evidence mismatch'):
                adapter.record_advisory_decision(root, decision, 'sessions/123', item)
            self.assertEqual((root/'state.json').read_bytes(), original)

    def test_existing_review_session_is_resumed_without_creating_another(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);adapter,item,decision = self._advisory_state_fixture(root)
            args = ['review', '--state-dir', str(root), '--target-slug', 'test-article', '--target-content-sha256', 'a' * 64, '--item-id', item['id'], '--review-branch', 'kesher-video-review-123', '--evidence-root', 'evidence', '--review-session', 'sessions/123']
            message = adapter.FINAL_MARKER + '\n' + json.dumps(decision, ensure_ascii=False)
            with mock.patch('sys.argv', args), mock.patch.dict(os.environ, {'JULES_API_KEY': 'test-key'}), mock.patch.object(adapter.legacy, 'create_session', side_effect=AssertionError('do not duplicate review')), mock.patch.object(adapter.legacy, 'request_json', return_value={'state':'COMPLETED'}), mock.patch.object(adapter.legacy, 'list_activities', return_value=[{'agentMessaged': {'agentMessage':message}}]), mock.patch.object(adapter.legacy.subprocess, 'run', side_effect=AssertionError('do not publish')):
                self.assertEqual(adapter.main(), 0)
            self.assertEqual(json.loads((root/'state.json').read_text())['items'][0]['jules_advisory_review']['session'], 'sessions/123')

    def test_policy_has_exact_machine_version(self):
        reviewer = load_reviewer()
        policy = POLICY_PATH.read_text(encoding="utf-8")
        self.assertEqual(policy.count("Policy-Version: 1"), 1)
        self.assertEqual(reviewer.REMOTION_POLICY_VERSION, 1)
        self.assertIn("Policy-Version: 1", reviewer.load_remotion_policy())

    def test_approved_contract_is_exact_and_valid(self):
        reviewer = load_reviewer()
        decision = approved_decision(reviewer)
        reviewer.validate_structured_contract(decision)
        decision["unexpected"] = True
        with self.assertRaisesRegex(reviewer.ReviewError, "schema keys mismatch"):
            reviewer.validate_structured_contract(decision)

    def test_schema_and_policy_versions_are_fail_closed(self):
        reviewer = load_reviewer()
        decision = approved_decision(reviewer)
        decision["schema_version"] = 99
        with self.assertRaisesRegex(reviewer.ReviewError, "schema_version"):
            reviewer.validate_structured_contract(decision)
        decision = approved_decision(reviewer)
        decision["policy_version"] = 99
        with self.assertRaisesRegex(reviewer.ReviewError, "policy_version"):
            reviewer.validate_structured_contract(decision)

    def test_top_level_decision_must_match_all_gates(self):
        reviewer = load_reviewer()
        decision = approved_decision(reviewer)
        decision["semantic_status"] = "rejected"
        with self.assertRaisesRegex(reviewer.ReviewError, "inconsistent"):
            reviewer.validate_structured_contract(decision)

    def test_rejection_requires_structured_quality_issue(self):
        reviewer = load_reviewer()
        decision = approved_decision(reviewer)
        decision["decision"] = "rejected"
        decision["visual_status"] = "rejected"
        decision["visual_note"] = "הפריימים חוזרים על אותה קומפוזיציה ולכן הסיפור החזותי אינו מתקדם באופן מספק"
        with self.assertRaisesRegex(reviewer.ReviewError, "must include blocking_issues"):
            reviewer.validate_structured_contract(decision)
        decision["blocking_issues"] = [
            {
                "gate": "visual",
                "code": "REPEATED_FRAMES",
                "message": "מספר פריימים חוזרים כמעט ללא שינוי ולכן נדרש בנייה מחודשת של התנועה",
            }
        ]
        reviewer.validate_structured_contract(decision)

    def test_prompt_declares_versioned_machine_contract_without_publication_authority(self):
        reviewer = load_reviewer(frame_count=3)
        prompt = reviewer.build_prompt(
            ".jules-video-review/fixture",
            {"id": "item-1"},
            {
                "manifest_sha256": "a" * 64,
                "final_sha256": "b" * 64,
                "transcript_sha256": "c" * 64,
                "source_file_sha256": "d" * 64,
                "visual_review_sha256": "e" * 64,
                "frame_sha256": {},
            },
        )
        self.assertIn("schema_version=1", prompt)
        self.assertIn("policy_version=1", prompt)
        self.assertIn("blocking_issues", prompt)
        self.assertIn("recommendations", prompt)
        self.assertIn("MUST NOT block upload", prompt)
        self.assertNotIn("Upload is allowed only when", prompt)


if __name__ == "__main__":
    unittest.main()
