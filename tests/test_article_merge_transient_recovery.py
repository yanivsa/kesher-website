from __future__ import annotations

import importlib.util
import io
import sys
import unittest
import urllib.error
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import scripts.kesher_content_controller_stabilized as stabilized

ROOT = Path(__file__).resolve().parents[1]
ARTICLE_CONTROLLER_PATH = ROOT / ".github" / "scripts" / "article-pr-controller.py"
ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


def load_article_controller():
    spec = importlib.util.spec_from_file_location("article_pr_controller_transient_recovery_test", ARTICLE_CONTROLLER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.payload


class ArticleMergeTransientRecoveryTests(unittest.TestCase):
    def test_image_loader_retries_transient_503_before_failing_gate(self) -> None:
        controller = load_article_controller()
        transient = urllib.error.HTTPError("https://raw.githubusercontent.com/example/image.jpg", 503, "between bytes timeout", hdrs=None, fp=io.BytesIO(b""))
        with mock.patch.object(controller.urllib.request, "urlopen", side_effect=[transient, _Response(b"image-bytes")]) as urlopen, mock.patch.object(controller.time, "sleep"):
            payload = controller.image_loader({"raw_url": "https://raw.githubusercontent.com/example/image.jpg"}, "token")

        self.assertEqual(payload, b"image-bytes")
        self.assertEqual(urlopen.call_count, 2)

    def test_successful_deferred_auto_merge_refunds_one_dispatch_idempotently(self) -> None:
        controller = stabilized.StabilizedRuntimeV5Controller(now=datetime(2026, 10, 25, 15, 30, tzinfo=ISRAEL_TZ), github=mock.MagicMock(), site=mock.MagicMock())
        state = {"cycle": "2026-10-25", "status": "article_pr_open", "article": {"pr_number": 1201, "current_pr_head_sha": "a" * 40, "merge_candidate_sha": "a" * 40, "merge_dispatch_count": 3}, "history": []}
        pr = {"number": 1201, "state": "open", "head": {"sha": "a" * 40}}
        notification = {"workflow": "Auto-merge Kesher article PRs", "run_id": "40194959063", "conclusion": "success", "source_slug": "", "slot": "2026-10-25", "source_sha": ""}

        with mock.patch.object(controller, "_child_notification_env", return_value=notification):
            first = controller._refund_deferred_auto_merge_success(state, pr)
            second = controller._refund_deferred_auto_merge_success(state, pr)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(state["article"]["merge_dispatch_count"], 2)
        self.assertEqual(state["article"]["last_refunded_auto_merge_run_id"], 40194959063)
        self.assertEqual(state["history"][-1]["reason"], "successful_deferred_auto_merge_refunded")


if __name__ == "__main__":
    unittest.main()
