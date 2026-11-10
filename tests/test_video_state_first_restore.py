from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import kesher_daily_pipeline as pipeline


class DurableMediaRestorePolicyTest(unittest.TestCase):
    @staticmethod
    def _item(status: str, **overrides):
        item = {
            "id": "video-exact",
            "type": "video_overview",
            "status": status,
            "technical_verified": False,
            "uploaded": False,
            "fresh_generation_attempt": 1,
            "source": {"slug": "target-slug", "content_sha256": "a" * 64},
        }
        item.update(overrides)
        return item

    def test_generating_state_does_not_require_heavy_media_restore(self):
        state = {"version": 1, "items": [self._item("generating", task_id="task", source_id="source")]}
        self.assertFalse(
            pipeline.durable_media_restore_required(
                state, operation="full", target_item_id="video-exact", target_slug="target-slug"
            )
        )

    def test_downloaded_and_upload_paths_require_heavy_media_restore(self):
        downloaded = {"version": 1, "items": [self._item("downloaded", raw_mp4="raw.mp4")]}
        self.assertTrue(
            pipeline.durable_media_restore_required(
                downloaded, operation="full", target_item_id="video-exact", target_slug="target-slug"
            )
        )
        self.assertTrue(
            pipeline.durable_media_restore_required(
                {"version": 1, "items": []}, operation="upload", target_slug="target-slug"
            )
        )

    def test_early_wrong_voice_retry_uses_lightweight_state_only(self):
        rejected = self._item(
            "rejected",
            failure_signature="wrong_narrator_gender",
            fresh_generation_attempt=1,
            raw_mp4="rejected.mp4",
            task_id="task-1",
        )
        state = {"version": 1, "items": [rejected]}
        self.assertFalse(
            pipeline.durable_media_restore_required(
                state, operation="full", target_item_id="video-exact", target_slug="target-slug"
            )
        )

    def test_final_wrong_voice_fallback_keeps_heavy_media_available(self):
        rejected = self._item(
            "rejected",
            failure_signature="wrong_narrator_gender",
            fresh_generation_attempt=3,
            raw_mp4="fallback.mp4",
            task_id="task-3",
        )
        state = {"version": 1, "items": [rejected]}
        self.assertTrue(
            pipeline.durable_media_restore_required(
                state, operation="full", target_item_id="video-exact", target_slug="target-slug"
            )
        )


class VideoWorkflowStateFirstRestoreTest(unittest.TestCase):
    @staticmethod
    def _workflow() -> str:
        return Path(".github/workflows/kesher-daily-video.yml").read_text(encoding="utf-8")

    @classmethod
    def _restore_script(cls) -> str:
        workflow = cls._workflow()
        start_idx = workflow.find("- name: Restore newest valid durable pipeline state")
        if start_idx < 0:
            raise AssertionError("restore step missing")
        run_idx = workflow.find("run: |", start_idx)
        end_idx = workflow.find("- name: Seed an exact orphaned-task recovery state", run_idx)
        script = workflow[run_idx + 6:end_idx].strip()
        lines = script.split("\n")
        indent = len(lines[0]) - len(lines[0].lstrip())
        return "\n".join(line[indent:] if line.startswith(" " * indent) else line for line in lines)

    def test_workflow_restores_lightweight_state_before_optional_heavy_media(self):
        workflow = self._workflow()
        restore = workflow[
            workflow.find("- name: Restore newest valid durable pipeline state"):
            workflow.find("- name: Seed an exact orphaned-task recovery state")
        ]
        light_query = "actions/artifacts?name=kesher-video-controller-state&per_page=100"
        heavy_query = "actions/artifacts?name=kesher-video-state&per_page=100"
        self.assertIn(light_query, restore)
        self.assertIn(heavy_query, restore)
        self.assertLess(restore.find(light_query), restore.find(heavy_query))
        self.assertIn("--requires-durable-media-restore", restore)
        self.assertIn("Skipping durable media hydration", restore)

        persist = workflow[
            workflow.find("- name: Persist lightweight controller state"):
            workflow.find("- name: Persist latest state and media evidence")
        ]
        self.assertIn("notebooklm-storage-state.json.enc", persist)
        self.assertIn("google-oauth2.json.enc", persist)

    def test_lightweight_generating_state_skips_heavy_artifact_download(self):
        script = self._restore_script()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_dir = root / "state"
            mock_bin = root / "bin"
            mock_bin.mkdir()
            fixture = root / "controller"
            fixture.mkdir()
            (fixture / "state.json").write_text(
                '{"version":1,"items":[{"id":"video-exact","type":"video_overview","status":"generating","uploaded":false,"technical_verified":false,"fresh_generation_attempt":1,"source":{"slug":"target-slug","content_sha256":"' + "a" * 64 + '"}}]}',
                encoding="utf-8",
            )
            archive = root / "controller.zip"
            subprocess.run(["zip", "-q", "-0", str(archive), "state.json"], cwd=fixture, check=True)

            gh = mock_bin / "gh"
            gh.write_text(
                f'''#!/usr/bin/env bash
set -e
if [[ "$*" == *"actions/artifacts?name=kesher-video-controller-state"* ]]; then
    printf '10\\t100\\n'
    exit 0
fi
if [[ "$*" == *"actions/artifacts/10/zip"* ]]; then
    cat "{archive}"
    exit 0
fi
if [[ "$*" == *"actions/artifacts?name=kesher-video-state"* ]]; then
    touch "{root / 'heavy-called'}"
    exit 99
fi
echo "Unexpected gh call: $*" >&2
exit 1
''',
                encoding="utf-8",
            )
            gh.chmod(0o755)

            python = mock_bin / "python"
            python.write_text(
                '''#!/usr/bin/env bash
if [[ "$*" == *"--requires-durable-media-restore"* ]]; then
    echo false
    exit 0
fi
if [[ "$*" == *"--report-json"* ]]; then
    echo '{"mocked":true}'
    exit 0
fi
exec /usr/bin/python3 "$@"
''',
                encoding="utf-8",
            )
            python.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{mock_bin}:{env.get('PATH', '')}"
            env["GITHUB_REPOSITORY"] = "test/repo"
            env["KESHER_STATE_DIR"] = str(state_dir)
            env.pop("KESHER_STATE_FILE", None)  # Production only supplies KESHER_STATE_DIR.
            env["RESTORE_OPERATION"] = "full"
            env["RESTORE_TARGET_ITEM_ID"] = "video-exact"
            env["RESTORE_TARGET_SLUG"] = "target-slug"

            result = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Restored valid lightweight controller state artifact 10", result.stdout)
            self.assertIn("Skipping durable media hydration", result.stdout)
            self.assertFalse((root / "heavy-called").exists())
            self.assertTrue((state_dir / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
