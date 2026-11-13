"""Native NotebookLM path: strict source and origin checks without Remotion."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.kesher_runtime.native_media import (
    _identity_digest, native_render_requested, render_native_provider,
    native_short_dimensions_valid,
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    streams = data["streams"]
    video = next(x for x in streams if x["codec_type"] == "video")
    audio = next(x for x in streams if x["codec_type"] == "audio")
    return {
        "width": video["width"], "height": video["height"],
        "duration": float(data["format"]["duration"]),
        "codec": video["codec_name"], "audio_codec": audio["codec_name"],
    }


def atomic_json_write(path, value):
    Path(path).write_text(json.dumps(value), encoding="utf-8")


class NativeProviderTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.raw = self.root / "original.mp4"
        self.raw.write_bytes(b"synthetic source placeholder")
        self.signature = self.root / "signature-mask.svg"
        self.signature.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50">'
            '<rect width="100" height="50" fill="black"/></svg>', encoding="utf-8")
        self.core = SimpleNamespace(
            STATE_DIR=self.root, sha256_file=sha256, PipelineError=RuntimeError,
            atomic_json_write=atomic_json_write, ffprobe=lambda path: {
                "width": 1280, "height": 720, "duration": 123.0,
                "codec": "h264", "audio_codec": "aac",
            },
        )
        self.item = {
            "id": "media-test-native-001",
            "raw_sha256": sha256(self.raw),
            "source": {"slug": "test-gratitude", "content_sha256": "a" * 64},
            "notebook_id": "notebook", "source_id": "source",
            "task_id": "task", "artifact_id": "artifact", "type": "video_overview",
        }

    def test_native_default_and_only_explicit_legacy(self):
        with patch.dict(os.environ, {"KESHER_MEDIA_RENDERER": ""}):
            with self.assertRaises(ValueError):
                native_render_requested()
        with patch.dict(os.environ, {"KESHER_MEDIA_RENDERER": "notebooklm-native"}):
            self.assertTrue(native_render_requested())
        with patch.dict(os.environ, {"KESHER_MEDIA_RENDERER": "remotion"}):
            self.assertFalse(native_render_requested())

    def test_source_changed_blocks_before_render(self):
        self.raw.write_bytes(b"changed")
        with self.assertRaisesRegex(RuntimeError, "SOURCE_HASH_MISMATCH"):
            render_native_provider(self.core, self.raw, self.item,
                                   kind="overview", signature_path=self.signature)

    def test_native_short_accepts_only_exact_9_by_16_hd_or_full_hd(self):
        for dimensions in ((720, 1280), (1080, 1920)):
            self.assertTrue(native_short_dimensions_valid(*dimensions))
        for dimensions in ((1280, 720), (1920, 1080), (360, 640), (720, 1200)):
            self.assertFalse(native_short_dimensions_valid(*dimensions))

    def test_no_landscape_short_or_fallback(self):
        self.item.update({
            "source_mode": "direct-short",
            "provider_video_format": "short",
            "provider_short_fallback_used": False,
        })
        with self.assertRaisesRegex(RuntimeError, "SHORT_NOT_PROVIDER_PORTRAIT"):
            render_native_provider(self.core, self.raw, self.item,
                                   kind="short", signature_path=self.signature)

    def test_identity_changes_with_provider_and_source(self):
        first = _identity_digest(self.core, self.raw, self.item, self.signature, "overview")
        second = _identity_digest(self.core, self.raw,
                                  {**self.item, "task_id": "another-task"}, self.signature, "overview")
        self.assertNotEqual(first, second)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg absent")
    def test_native_overlay_preserves_audio_and_source_proof(self):
        try:
            import cairosvg  # noqa: F401
        except ImportError:
            # The trusted CI suite intentionally does not install media extras.
            # Exercise the actual FFmpeg/source-audio/signature-proof path with
            # a minimal PNG rasterization stub; production uses pinned CairoSVG.
            import base64
            import sys
            from types import ModuleType

            fake = ModuleType("cairosvg")
            black_pixel = (
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
                "AAAADUlEQVR4nGNgYGD4DwABBAEAX+XDSwAAAABJRU5ErkJggg=="
            )
            fake.svg2png = lambda *, write_to, **kwargs: Path(write_to).write_bytes(
                base64.b64decode(black_pixel)
            )
            rasterizer = patch.dict(sys.modules, {"cairosvg": fake})
            rasterizer.start()
            self.addCleanup(rasterizer.stop)
        source = self.root / "sample.mp4"
        source.unlink(missing_ok=True)
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=blue:s=640x360:r=15",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
            "-t", "2.5", "-c:v", "libx264", "-c:a", "aac", str(source),
        ]
        subprocess.run(command, check=True, capture_output=True, timeout=50)
        self.item["raw_sha256"] = sha256(source)
        self.core.ffprobe = probe
        output = render_native_provider(
            self.core, source, self.item, kind="overview", signature_path=self.signature)
        self.assertTrue(output.is_file())
        self.assertEqual(self.item["visual_pipeline"], "notebooklm-native-signature-v1")
        self.assertEqual(sha256(source), self.item["raw_sha256"])
        self.assertNotEqual(sha256(output), self.item["raw_sha256"])
        from scripts.kesher_e2e_delivery_guard import _signature_verified
        self.assertTrue(_signature_verified(self.item))
        # Second call must reuse exactly the verified bytes, never re-render.
        final_sha = sha256(output)
        self.assertEqual(render_native_provider(
            self.core, source, self.item, kind="overview",
            signature_path=self.signature), output)
        self.assertEqual(sha256(output), final_sha)


if __name__ == "__main__":
    unittest.main()
