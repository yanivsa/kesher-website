import unittest
import io
import json
from datetime import datetime, timezone
from unittest import mock

from scripts.kesher_content_controller_stabilized import StabilizedRuntimeV5Controller


class PreImageTextRepairTests(unittest.TestCase):
    def test_real_adapter_sends_jules_request_and_exact_head_marker_before_image(self):
        github = mock.MagicMock(repo="yanivsa/kesher-website", token="test-token")
        controller = StabilizedRuntimeV5Controller(github, mock.MagicMock())
        head = "b" * 40
        pr = {"number": 1213, "head": {"sha": head, "ref": "same-branch"},
              "body": "https://jules.google.com/task/5215839896508682722"}
        writes = []

        def http(request, **kwargs):
            url = request.full_url
            if request.method == "GET" and "/issues/1213/comments" in url:
                return io.BytesIO(b"[]")
            writes.append((url, json.loads(request.data)))
            return io.BytesIO(b"{}")

        with mock.patch.dict("os.environ", {"JULES_API_KEY": "test-key"}), mock.patch("urllib.request.urlopen", side_effect=http):
            result = controller._request_article_text_repair(pr, ["evidence_missing"])
        self.assertTrue(result)
        self.assertEqual([u for u, _ in writes], [
            "https://jules.googleapis.com/v1alpha/sessions/5215839896508682722:sendMessage",
            "https://api.github.com/repos/yanivsa/kesher-website/issues/1213/comments",
        ])
        self.assertIn("SAME PR #1213", writes[0][1]["prompt"])
        self.assertIn("evidence_missing", writes[0][1]["prompt"])
        self.assertIn("attempt=1 head=" + head, writes[1][1]["body"])

    def test_missing_content_metadata_requests_same_pr_repair_without_merge_or_image(self):
        github = mock.MagicMock()
        controller = StabilizedRuntimeV5Controller(github, mock.MagicMock(), now=datetime(2026, 10, 26, tzinfo=timezone.utc))
        head = "a" * 40
        state = {"cycle": "2026-10-26", "status": "article_pr_open", "article": {
            "status": "running", "normalized_head_sha": head, "merge_dispatch_count": 0,
        }, "image": {"status": "pending", "attempt_count": 0}, "history": []}
        pr = {"number": 1213, "head": {"sha": head}, "body": ""}
        controller._pr_repair_status = lambda _: (0, set())
        github.article_pr_normalization_required.return_value = (False, "2026-10-26")
        # This is the observed catalog boundary: owned article missing evidence and serviceUrl.
        post = {"id": "municipal-kindergarten-adjustment", "controllerManaged": True,
                "date": "2026-10-26", "content": " ".join(["word"] * 800) + "<h3>x</h3>" * 5}
        github.contents_json.side_effect = [[post], []]
        repairs = []
        controller._request_article_text_repair = lambda target, errors: repairs.append((target["number"], errors)) or True
        action = controller._handle_open_article_pr(state, pr)
        self.assertEqual(action.kind, "request_text_repair")
        self.assertEqual(repairs[0][0], 1213)
        self.assertTrue(any("evidence_missing" in e for e in repairs[0][1]))
        self.assertEqual(state["article"]["merge_dispatch_count"], 0)
        self.assertEqual(state["image"], {"status": "pending", "attempt_count": 0})
        github.dispatch.assert_not_called()

    def test_repair_cannot_silently_wait_when_credentials_are_missing(self):
        github = mock.MagicMock()
        controller = StabilizedRuntimeV5Controller(github, mock.MagicMock())
        with mock.patch.dict("os.environ", {"JULES_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "JULES_REPAIR_CREDENTIAL_MISSING"):
                controller._request_article_text_repair({"number": 1213}, ["evidence_missing"])
