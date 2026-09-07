#!/usr/bin/env python3
"""Unit tests for deterministic Hebrew voice synthesis module."""

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from scripts.generate_hebrew_voice import synthesize_hebrew_voice, VoiceSynthesisError, DEFAULT_EDGE_VOICE


class HebrewVoiceSynthesisTests(unittest.TestCase):
    def test_empty_text_raises_error(self):
        with self.assertRaises(VoiceSynthesisError):
            synthesize_hebrew_voice("", Path("/tmp/test.mp3"))

    def test_whitespace_text_raises_error(self):
        with self.assertRaises(VoiceSynthesisError):
            synthesize_hebrew_voice("   \n\t  ", Path("/tmp/test.mp3"))

    @patch("scripts.generate_hebrew_voice.synthesize_edge_tts")
    @patch("scripts.generate_hebrew_voice.estimate_voice_pitch")
    def test_successful_synthesis_passes_female_pitch(self, mock_pitch, mock_edge):
        mock_pitch.return_value = 210.0  # Typical Israeli female voice pitch
        target = Path("/tmp/test_voice_success.mp3")
        
        result = synthesize_hebrew_voice("שלום שמי שירה", target)
        self.assertEqual(result, target)
        mock_edge.assert_called_once_with("שלום שמי שירה", target, voice=DEFAULT_EDGE_VOICE)

    @patch("scripts.generate_hebrew_voice.synthesize_edge_tts")
    @patch("scripts.generate_hebrew_voice.estimate_voice_pitch")
    def test_male_pitch_fails_female_pitch_check(self, mock_pitch, mock_edge):
        mock_pitch.return_value = 110.0  # Male pitch
        target = Path("/tmp/test_voice_male.mp3")
        target.touch()

        with self.assertRaises(VoiceSynthesisError) as ctx:
            synthesize_hebrew_voice("שלום שמי שירה", target)
        self.assertIn("failed female pitch check", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
