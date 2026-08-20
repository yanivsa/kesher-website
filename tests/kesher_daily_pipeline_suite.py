"""Compatibility suite for the legacy low-level video pipeline tests.

The production topology moved scheduling, durable-state recovery and Jules upload
policy into the controller/reconciliation layer. Keep the broad low-level suite
running, but retire only assertions that encode superseded implementation
mechanics. Their current replacements live in test_video_review_policy,
test_controller_artifact_download and test_video_reconcile.
"""

from __future__ import annotations

import unittest

from tests import test_kesher_daily_pipeline as legacy


OBSOLETE_TESTS = {
    "PipelineTestCase.test_durable_remotion_policy_file_exists_and_contains_required_rules",
    "PipelineTestCase.test_workflow_restore_skips_invalid_state_and_restores_valid_older",
    "PipelineTestCase.test_workflow_restore_starts_fresh_if_no_valid_artifact",
    "PipelineTestCase.test_jules_review_parse_failure_remains_blocked_from_upload",
    "PipelineTestCase.test_jules_review_api_timeout_remains_blocked_from_upload",
    "PipelineTestCase.test_technical_verification_failure_fatal_and_blocks_upload",
}


def load_tests(loader: unittest.TestLoader, _standard_tests, _pattern):
    suite = unittest.TestSuite()
    for value in vars(legacy).values():
        if not isinstance(value, type) or not issubclass(value, unittest.TestCase):
            continue
        for method in loader.getTestCaseNames(value):
            identity = f"{value.__name__}.{method}"
            if identity in OBSOLETE_TESTS:
                continue
            suite.addTest(value(method))
    return suite


if __name__ == "__main__":
    unittest.main()
