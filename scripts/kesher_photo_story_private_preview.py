#!/usr/bin/env python3
"""Private-only 18-second photographic Remotion motion proof.

No provider, no new YouTube upload, no real narration. It deliberately uses
synthetic audio so this must NEVER be treated as Overview voice/science QA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "research/kesher-vantage-photographic-private-preview.json"
EXPECTED_SLUG = "vantage-sensitivity-sensitive-gifted-children"
EXPECTED_SHA = "e264d2962b9028afc73463edcd2718b37539212762b0a72e35507d33dcb270ea"
IMAGE = re.compile(r"^images/(?:blog|generated/blog)/[a-z0-9-]+\.(?:jpg|jpeg|png|webp)$")
HEX = re.compile(r"^[a-f0-9]{64}$")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require_regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"PRIVATE_PREVIEW_MISSING_OR_SYMLINK: {path}")


def stage_photo_assets(plan: dict) -> list[dict]:
    if (plan.get("purpose") != "PRIVATE_VISUAL_PROOF_ONLY"
            or plan.get("no_publication") is not True
            or plan.get("synthetic_audio_only") is not True
            or plan.get("sourceBinding") != {
                "slug": EXPECTED_SLUG, "contentSha256": EXPECTED_SHA
            }):
        raise ValueError("PRIVATE_PREVIEW_SOURCE_AND_NO_UPLOAD_CONTRACT")
    story = plan["licensedPhotoStory"]
    if story["sourceSlug"] != EXPECTED_SLUG or story["contentSha256"] != EXPECTED_SHA:
        raise ValueError("PRIVATE_PREVIEW_STORY_SOURCE_CHANGED")
    scenes = story["scenes"]
    if not isinstance(scenes, list) or len(scenes) < 3:
        raise ValueError("PRIVATE_PREVIEW_NOT_ENOUGH_SCENES")
    previous_end = 0
    assets: set[str] = set()
    staged: list[dict] = []
    for item in scenes:
        path = item["assetPath"]
        if (not IMAGE.fullmatch(path) or path in assets
                or not HEX.fullmatch(item["assetSha256"])
                or not item["licenseEvidenceUrl"].startswith("https://")):
            raise ValueError("PRIVATE_PREVIEW_UNSAFE_OR_UNDOCUMENTED_IMAGE")
        assets.add(path)
        first, last = item["startFrame"], item["endFrame"]
        if (not isinstance(first, int) or not isinstance(last, int)
                or first != previous_end or last - first < 120):
            raise ValueError("PRIVATE_PREVIEW_GAP_OR_TOO_SHORT")
        previous_end = last
        src = ROOT / "public" / path
        require_regular(src)
        expected = item["assetSha256"]
        if digest(src) != expected:
            raise ValueError(f"PRIVATE_PREVIEW_ASSET_HASH_MISMATCH: {path}")
        dest = ROOT / "remotion-kesher/public" / path
        # Strictly local, never a symlink-driven escape from the preview tree.
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink():
            raise ValueError("PRIVATE_PREVIEW_DEST_SYMLINK")
        shutil.copyfile(src, dest)
        if digest(dest) != expected:
            raise ValueError("PRIVATE_PREVIEW_STAGED_HASH_MISMATCH")
        staged.append({"path": path, "sha256": expected})
    if previous_end != 540:
        raise ValueError("PRIVATE_PREVIEW_DURATION_NOT_18_SECONDS")
    return staged


def run(output: Path) -> dict:
    require_regular(PLAN)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    assets = stage_photo_assets(plan)
    remotion = ROOT / "remotion-kesher"
    dummy = remotion / "public/kesher-visual-proof-synthetic.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=#23423c:s=1280x720:r=30",
        "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000",
        "-t", "18", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", str(dummy),
    ], check=True, timeout=90)
    props = {
        "videoSrc": dummy.name,
        "title": "",
        "hook": "",
        "sourceDurationInFrames": 540,
        "beatLabels": [],
        "sourceBinding": plan["sourceBinding"],
        "licensedPhotoStory": plan["licensedPhotoStory"],
    }
    prop_path = output / "private-props.json"
    prop_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    binary = remotion / "node_modules/.bin/remotion"
    if not binary.is_file():
        raise RuntimeError("PRIVATE_PREVIEW_REMOTION_DEPENDENCIES_MISSING")
    preview = output / "vantage-photographic-private-18s.mp4"
    subprocess.run([
        str(binary), "render", "src/index.ts", "KesherVideo", str(preview),
        "--props", str(prop_path), "--codec=h264", "--crf=25",
        "--log=error",
    ], cwd=remotion, check=True, timeout=900)
    require_regular(preview)
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(preview),
    ], timeout=30))
    video = next((s for s in probe["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in probe["streams"] if s["codec_type"] == "audio"), None)
    if not video or (int(video["width"]), int(video["height"])) != (1280, 720):
        raise RuntimeError("PRIVATE_PREVIEW_INVALID_LANDSCAPE_RENDER")
    if not audio:
        raise RuntimeError("PRIVATE_PREVIEW_SYNTHETIC_AUDIO_STREAM_MISSING")
    for seconds in (3, 9, 15):
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", str(seconds), "-i", str(preview),
            "-frames:v", "1", str(output / f"frame-{seconds:02d}s.png")
        ], check=True, timeout=40)
    summary = {
        "status": "PRIVATE_VISUAL_PROOF_RENDERED",
        "source_slug": EXPECTED_SLUG,
        "source_sha256": EXPECTED_SHA,
        "video_sha256": digest(preview),
        "source_video_uploaded": False,
        "youtube_uploaded": False,
        "real_narration_included": False,
        "audio": "SYNTHETIC_TEST_TONE_NOT_PUBLIC_ORIGINAL",
        "quality": "QA_PENDING",
        "rights": "INDIVIDUAL_ASSET_LICENSE_QA_PENDING",
        "preview_seconds": 18,
        "preview_dimensions": "1280x720",
        "asset_evidence": assets,
    }
    (output / "preview-manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
