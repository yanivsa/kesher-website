from __future__ import annotations

# Runtime contract regression suite for the mandatory Jules review gate.
import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEWER_PATH = ROOT / "scripts" / "jules_video_reviewer.py"
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

    def test_rejection_requires_structured_blocking_issue(self):
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

    def test_prompt_declares_versioned_machine_contract(self):
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


if __name__ == "__main__":
    unittest.main()
