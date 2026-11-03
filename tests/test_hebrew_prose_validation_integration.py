import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.kesher_runtime import article_prose_audit


class HebrewProseValidationIntegrationTests(unittest.TestCase):
    @patch('scripts.kesher_runtime.article_prose_audit.subprocess.run')
    def test_report_helper_invokes_trusted_node_audit_and_returns_result(self, run):
        run.return_value = Mock(
            returncode=0,
            stdout=json.dumps({
                'id': 'candidate-post',
                'risk': 'watch',
                'riskPoints': 1,
                'findings': [{'category': 'punctuation-cadence'}],
                'advisories': [],
            }),
            stderr='',
        )
        post = {'id': 'candidate-post', 'title': 'כותרת', 'excerpt': '', 'content': '<p>תוכן</p>'}
        result = article_prose_audit._run_prose_audit(post)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['risk'], 'watch')
        args, kwargs = run.call_args
        self.assertEqual(args[0][0], 'node')
        self.assertTrue(str(args[0][1]).endswith('scripts/hebrew-prose-audit.cjs'))
        self.assertIn('--post-stdin', args[0])
        self.assertEqual(json.loads(kwargs['input'])['id'], 'candidate-post')
        self.assertFalse(kwargs.get('shell', False))
        self.assertEqual(kwargs['timeout'], 10)

    @patch('scripts.kesher_runtime.article_prose_audit.subprocess.run')
    def test_report_helper_failure_is_advisory_not_validation_failure(self, run):
        run.side_effect = subprocess.TimeoutExpired(cmd=['node'], timeout=10)
        result = article_prose_audit._run_prose_audit({'id': 'candidate-post'})
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['risk'], 'unknown')

    @patch('scripts.kesher_runtime.article_prose_audit.report_candidate')
    def test_cli_always_returns_success_for_report_only_boundary(self, report):
        report.side_effect = RuntimeError('unexpected audit failure')
        with patch('scripts.kesher_runtime.article_prose_audit._emit'):
            self.assertEqual(article_prose_audit.main(['command-id']), 0)

    def test_validation_workflow_runs_prose_audit_as_non_blocking_step(self):
        text = Path('.github/workflows/kesher-article-validation.yml').read_text()
        marker = '- name: Report Hebrew prose quality'
        self.assertIn(marker, text)
        block = text[text.index(marker):]
        block = block.split('\n      - name:', 1)[0]
        self.assertIn('continue-on-error: true', block)
        self.assertIn('GH_TOKEN: ${{ github.token }}', block)
        self.assertIn('python -m scripts.kesher_runtime.article_prose_audit "$COMMAND_ID"', block)


if __name__ == '__main__':
    unittest.main()
