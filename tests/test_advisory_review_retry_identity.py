import os
from pathlib import Path
import subprocess
import unittest

import yaml


class AdvisoryReviewRetryIdentityTests(unittest.TestCase):
    def run_preflight(self, item):
        path = Path(__file__).resolve().parents[1] / '.github/workflows/kesher-video-advisory-review.yml'
        steps = yaml.safe_load(path.read_text())['jobs']['review']['steps']
        script = next(s['run'] for s in steps if s['name'] == 'Validate exact advisory evidence identity')
        return subprocess.run(['bash', '-c', script], env={**os.environ,
            'REVIEW_BRANCH': 'kesher-video-review-40314746817',
            'EVIDENCE_ROOT': '.jules-video-review/40314746817',
            'REVIEW_ITEM_ID': item, 'TARGET_CONTENT_SHA256': 'd' * 64,
        }, capture_output=True, text=True)

    def test_real_preflight_accepts_initial_and_bounded_retry_items(self):
        base = 'video-20261026-131504-d4ece4f847'
        for item in [base, base + '-a2', base + '-a3']:
            with self.subTest(item=item):
                result = self.run_preflight(item)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_preflight_refuses_unbounded_or_malformed_retry_items(self):
        base = 'video-20261026-131504-d4ece4f847'
        for item in [base + '-a1', base + '-a4', base + '-a20', base + '/../../main']:
            with self.subTest(item=item):
                self.assertNotEqual(self.run_preflight(item).returncode, 0)
