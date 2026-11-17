"""Hermetic gates for source-bound historical NotebookLM *read-only* audit.

The old CLI printed only 100 of 340 videos. A missing ID in that display
is not evidence that a provider task is absent, and can never grant creation.
"""
import re
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/kesher-daily-video.yml"


def audit_code():
    text = WORKFLOW.read_text(encoding="utf-8")
    block = text.split(
        "      - name: Inventory existing native NotebookLM source and video IDs without mutation\n", 1
    )[1].split("\n      - name:", 1)[0]
    code = block.split("          python3 - <<'PY'\n", 1)[1].rsplit("\n          PY", 1)[0]
    return textwrap.dedent(code), block, text


class SourceBoundProviderReadbackTests(unittest.TestCase):
    def test_embedded_preflight_python_compiles_without_running(self):
        code, _, _ = audit_code()
        compile(code, str(WORKFLOW), "exec")

    def test_every_recovered_uuid_is_inspected_from_full_list(self):
        code, _, _ = audit_code()
        expected = (
            "077ede84-dd9c-4a07-b2b6-56acdad27be7",
            "5b742ce5-3bd4-421a-aaea-02641f3e10d0",
            "63b37426-9fd2-49e3-a2ce-a412fc347484",
            "12c218a9-9912-4f65-869b-3517cacb57a6",
            "488e8ec8-264f-48c3-88ff-b17df3f9b1d6",
            "1495a541-b862-4d28-b855-28f1a1eef03d",
            "57b334e9-772d-4c58-837b-bc8fe24c4df2",
            "7e7cabb9-7d29-43a7-8e52-a0932f6a4452",
        )
        for task in expected:
            self.assertEqual(code.count(task), 1)
        self.assertIn("for item in rows:", code)
        self.assertIn("for row in rows[-100:]:", code)
        self.assertLess(code.index("for item in rows:"), code.index("for row in rows[-100:]:"))
        self.assertIn("NOTEBOOKLM_EXACT_TASK_DUPLICATE_ID", code)

    def test_no_claim_of_source_ownership_completeness_or_dispatch(self):
        code, block, _ = audit_code()
        for forbidden in ("gh workflow run", "youtube upload", "notebooklm.generate", "requests.post"):
            self.assertNotIn(forbidden, block.lower())
        for required in (
            "'source_verified': False", "'catalog_complete': False",
            "'generation_authorized': False", "'upload_authorized': False",
            "NOTEBOOKLM_EXACT_TASK_DUPLICATE_ID",
        ):
            self.assertIn(required, code)

    def test_only_preflight_and_after_credential_materialization(self):
        _, block, full = audit_code()
        self.assertIn("inputs.operation == 'preflight'", block)
        self.assertLess(full.index("Materialize NotebookLM credentials without exposing them"),
                        full.index("Inventory existing native NotebookLM source and video IDs"))
        self.assertLess(full.index("Refuse emergency bridge after cutover exclusion begins"),
                        full.index("Inventory existing native NotebookLM source and video IDs"))


if __name__ == "__main__":
    unittest.main()
