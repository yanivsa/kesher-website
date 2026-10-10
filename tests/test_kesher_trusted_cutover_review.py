"""Fresh-review regressions for trusted cutover composition."""
from __future__ import annotations

import json
import os
import types
import unittest
from unittest.mock import patch

from scripts.kesher_runtime.state import StateInvalid
from tests.test_kesher_trusted_cutover_service import TrustedCutoverServiceTests


class TrustedCutoverFreshReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = TrustedCutoverServiceTests("test_complete_bundle_composes_existing_runtime_identity_and_application")
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def _application(self, module):
        def application(**kwargs):
            return types.SimpleNamespace(**kwargs)

        stack = (
            patch.object(module, "build_runtime", return_value=object()),
            patch.object(module, "ActionsIdentity", return_value=object()),
            patch.object(module, "CutoverApplication", side_effect=application),
            patch.object(module, "_verify_installed_review", return_value=None),
        )
        return stack

    def test_review_file_drift_refuses_before_runtime_step(self):
        module = self.fixture.load_module()
        p1, p2, p3, p4 = self._application(module)
        with patch.dict(os.environ, self.fixture.env, clear=True), p1, p2, p3, p4:
            application = module.build()
            review_path = self.fixture.root / "review.json"
            changed = json.loads(review_path.read_text(encoding="utf-8"))
            changed["main_sha"] = "9" * 40
            review_path.write_text(json.dumps(changed, sort_keys=True), encoding="utf-8")
            with self.assertRaisesRegex(StateInvalid, "CUTOVER_INSTALLED_CONFIGURATION_CHANGED"):
                application.review_check()

    def test_environment_binding_drift_refuses_before_runtime_step(self):
        module = self.fixture.load_module()
        p1, p2, p3, p4 = self._application(module)
        with patch.dict(os.environ, self.fixture.env, clear=True), p1, p2, p3, p4:
            application = module.build()
            os.environ["KESHER_CUTOVER_EPOCH"] = "different-epoch"
            with self.assertRaisesRegex(StateInvalid, "CUTOVER_INSTALLED_CONFIGURATION_CHANGED"):
                application.review_check()


if __name__ == "__main__":
    unittest.main()
