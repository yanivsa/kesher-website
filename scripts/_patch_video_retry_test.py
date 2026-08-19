#!/usr/bin/env python3
from pathlib import Path

path = Path('tests/test_kesher_daily_pipeline.py')
text = path.read_text(encoding='utf-8')
old = '''    @mock.patch.object(reviewer, "validate_decision")\n    @mock.patch.object(reviewer, "wait_for_message")\n    @mock.patch.object(reviewer, "create_session")\n    def test_jules_review_replaces_timed_out_session_autonomously(\n        self,\n        create: mock.Mock,\n        wait: mock.Mock,\n        validate: mock.Mock,\n    ) -> None:\n'''
new = '''    @mock.patch.object(reviewer, "validate_structured_contract")\n    @mock.patch.object(reviewer, "validate_decision")\n    @mock.patch.object(reviewer, "wait_for_message")\n    @mock.patch.object(reviewer, "create_session")\n    def test_jules_review_replaces_timed_out_session_autonomously(\n        self,\n        create: mock.Mock,\n        wait: mock.Mock,\n        validate: mock.Mock,\n        validate_contract: mock.Mock,\n    ) -> None:\n'''
if text.count(old) != 1:
    raise SystemExit('retry test decorator target not unique')
text = text.replace(old, new, 1)
old_assert = '''        self.assertEqual(create.call_count, 2)\n        validate.assert_called_once()\n'''
new_assert = '''        self.assertEqual(create.call_count, 2)\n        validate.assert_called_once()\n        validate_contract.assert_called_once_with(decision)\n'''
if text.count(old_assert) != 1:
    raise SystemExit('retry test assertion target not unique')
path.write_text(text.replace(old_assert, new_assert, 1), encoding='utf-8')
