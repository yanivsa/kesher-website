#!/usr/bin/env python3
"""Deterministic, category-agnostic visual motion planning for Kesher Short V4."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

SAMPLE_WIDTH = 48
SAMPLE_HEIGHT = 84


def salient_focus_from_gray(data: bytes, width: int, height: int) -> tuple[float, float, float]:
    """Return normalized high-contrast centroid and mean gradient energy."""
    if width < 3 or height < 3 or len(data) != width * height:
        raise ValueError("invalid grayscale frame")
    total = 0.0
    weighted_x = 0.0
    weighted_y = 0.0
    samples = 0
    for y in range(1, height - 1):
        row = y * width
        for x in range(1, width - 1):
            index = row + x
            value = data[index]
            score = (
                abs(value - data[index - 1])
                + abs(value - data[index + 1])
                + abs(value - data[index - width])
                + abs(value - data[index + width])
            )
            total += score
            weighted_x += score * x
            weighted_y += score * y
            samples += 1
    if total <= 0:
        return 0.5, 0.5, 0.0
    return (
        round(weighted_x / total / (width - 1), 4),
        round(weighted_y / total / (height - 1), 4),
        round(total / max(1, samples), 3),
    )


def sample_focus(video_path: Path, timestamp: float) -> tuple[float, float, float]:
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        (
            f"scale={SAMPLE_WIDTH}:{SAMPLE_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={SAMPLE_WIDTH}:{SAMPLE_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=gray"
        ),
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    result = subprocess.run(command, capture_output=True, timeout=60, check=False)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace")[-400:]
        raise RuntimeError(f"visual sampling failed at {timestamp:.3f}s: {detail}")
    return salient_focus_from_gray(result.stdout, SAMPLE_WIDTH, SAMPLE_HEIGHT)


def build_motion_plan(video_path: Path, duration_seconds: float, fps: int = 30) -> dict[str, Any]:
    """Build normalized timestamped targets from the actual source video's pixels."""
    duration = float(duration_seconds)
    if duration <= 0:
        raise ValueError("duration must be positive")
    sample_count = max(5, min(9, round(duration / 6.0)))
    segment_seconds = duration / sample_count
    targets: list[dict[str, Any]] = []
    for index in range(sample_count):
        timestamp = min(duration - 0.001, (index + 0.5) * segment_seconds)
        focus_x, focus_y, energy = sample_focus(video_path, timestamp)
        # Strong enough to be visible, capped to keep text/faces readable.
        zoom = round(1.12 + min(0.10, energy / 1800.0), 4)
        rotation = round((0.32 if index % 2 == 0 else -0.32) * min(1.0, 0.55 + energy / 220.0), 4)
        start_frame = round(index * segment_seconds * fps)
        end_frame = max(start_frame + 1, round((index + 1) * segment_seconds * fps) - 1)
        targets.append(
            {
                "startFrame": start_frame,
                "endFrame": end_frame,
                "timestampSeconds": round(timestamp, 3),
                "focusX": focus_x,
                "focusY": focus_y,
                "zoom": zoom,
                "rotation": rotation,
                "salienceEnergy": energy,
            }
        )
    return {
        "schemaVersion": 1,
        "planner": "pixel-gradient-centroid-v1",
        "fps": fps,
        "durationSeconds": round(duration, 3),
        "sampleCount": sample_count,
        "targets": targets,
    }
