"""Real media regression: rendering cannot silently replace or shift source audio."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import kesher_daily_pipeline as core
from scripts.kesher_runtime.render_provenance import record_signature


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'real media tools unavailable')
class SourceAudioPreservationTests(unittest.TestCase):
    def test_recorded_render_retains_decoded_source_audio_exactly_even_when_renderer_changed_it(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(core, 'STATE_DIR', Path(folder)):
            root = Path(folder)
            raw, final = root / 'raw.mp4', root / 'rendered.mp4'
            for path, frequency in [(raw, 440), (final, 880)]:
                subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:r=30',
                    '-f', 'lavfi', '-i', f'sine=frequency={frequency}:sample_rate=48000',
                    '-t', '2', '-c:v', 'libx264', '-c:a', 'aac', str(path)], check=True, timeout=60)
            def pcm(path):
                return subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vn', '-ac', '1', '-ar', '16000',
                    '-f', 's16le', '-'], capture_output=True, check=True, timeout=60).stdout
            source_audio = pcm(raw)
            self.assertNotEqual(source_audio, pcm(final))
            asset = core.PROJECT_DIR / core.SIGNATURE_SOURCE
            item = {'id': 'audio-proof', 'type': 'video_overview', 'content_duration_seconds': 2.0}
            record_signature(core, raw, final, item, asset, core.ffprobe(raw), core.ffprobe(final))
            self.assertEqual(source_audio, pcm(final))
            self.assertEqual(core.ffprobe(final)['duration'], 2.0)
            self.assertTrue(item['signature_verified'])


if __name__ == '__main__':
    unittest.main()
