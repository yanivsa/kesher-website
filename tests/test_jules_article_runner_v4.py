from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import jules_article_runner_v4 as runner


class JulesArticleRunnerV4Tests(unittest.TestCase):
    def test_failure_diagnostic_is_persisted_for_preserved_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(
                json.dumps({
                    "outcome": "JULES_TIMEOUT_SESSION_ACTIVE",
                    "message": "session preserved",
                    "session_id": "sessions/123",
                }),
                encoding="utf-8",
            )
            diagnostic = {
                "activity_count": 4,
                "change_set_count": 1,
                "last_agent_message": "waiting on repository step",
            }
            with mock.patch.dict(
                "os.environ",
                {"JULES_API_KEY": "key", "KESHER_ARTICLE_RESULT_PATH": str(path)},
                clear=False,
            ), mock.patch.object(
                runner.v3.diagnostics, "diagnose", return_value=diagnostic
            ) as diagnose, mock.patch.object(
                runner.v3.diagnostics, "attach_to_result"
            ) as attach:
                runner.attach_failure_diagnostic()

        diagnose.assert_called_once_with("key", "sessions/123")
        attach.assert_called_once_with(path, diagnostic)


if __name__ == "__main__":
    unittest.main()
