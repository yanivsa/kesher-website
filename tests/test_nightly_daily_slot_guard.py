"""Regression checks for the nightly controller's read-only slot guard."""
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import yaml

WORKFLOW = Path(".github/workflows/kesher-content-controller.yml")


class NightlyDailySlotGuardTests(unittest.TestCase):
    def run_guard(self, historical=None, recent=None, prs=None, runs=None):
        job = yaml.safe_load(WORKFLOW.read_text())["jobs"]["nightly_daily"]
        shell = next(step["run"] for step in job["steps"] if step.get("id") == "guard")
        code = shell.split("python3 - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        sha = "a" * 40
        responses = {
            "pulls?state=open&per_page=100": prs or [],
            "actions/workflows/kesher-publish-request.yml/runs?per_page=100": {
                "workflow_runs": runs or []
            },
            "branches/main": {"commit": {"sha": sha}},
            f"contents/src/data/posts.json?ref={sha}": [] if historical is None else historical,
            f"contents/src/data/postsRecent.json?ref={sha}": [] if recent is None else recent,
        }

        def request(command, **kwargs):
            endpoint = command[-1].split("/repos/owner/repo/", 1)[1]
            if isinstance(responses[endpoint], Exception):
                raise responses[endpoint]
            if endpoint.startswith("contents/"):
                self.assertIn("Accept: application/vnd.github.raw+json", command)
            return json.dumps(responses[endpoint])

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            with patch.dict(os.environ, {"REPO": "owner/repo", "GITHUB_OUTPUT": str(output)}), patch(
                "subprocess.check_output", side_effect=request
            ):
                exec(compile(code, "<nightly guard>", "exec"), {})
            return output.read_text()

    def test_empty_slot_can_dispatch(self):
        self.assertIn("allow=true", self.run_guard())

    def test_existing_article_in_either_catalog_blocks_new_dispatch(self):
        today = datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat()
        post = {"date": today, "slug": "existing-article"}
        for kwargs in ({"historical": [post]}, {"recent": [post]}):
            with self.subTest(kwargs=kwargs):
                self.assertIn("allow=false", self.run_guard(**kwargs))

    def test_existing_candidate_or_active_publisher_blocks_dispatch(self):
        today = datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat()
        pr = {"number": 12, "head": {"ref": "content/kesher-example"}, "body": f"Publication slot: `{today}`"}
        self.assertIn("allow=false", self.run_guard(prs=[pr]))
        self.assertIn("allow=false", self.run_guard(runs=[{"id": 42, "status": "in_progress"}]))

    def test_malformed_or_unavailable_catalog_fails_closed(self):
        with self.assertRaises(ValueError):
            self.run_guard(recent={"posts": []})
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_guard(historical=subprocess.CalledProcessError(1, "gh"))

    def test_dispatch_resolves_repo_without_checkout(self):
        job = yaml.safe_load(WORKFLOW.read_text())["jobs"]["nightly_daily"]
        step = next(s for s in job["steps"] if s["name"].startswith("Dispatch KESHER"))
        self.assertEqual(step["env"]["GH_REPO"], "${{ github.repository }}")
        self.assertIn("-f action=daily", step["run"])


if __name__ == "__main__":
    unittest.main()
