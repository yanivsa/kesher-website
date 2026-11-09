#!/usr/bin/env python3
"""Render a private research-bound Hebrew KESHER Overview; NEVER publish.

Reuses the previously licensed BlueTTS synthesis implementation. The canonical
published item and its public URL are read-only; these new bytes are for honest
independent visual/semantic/audio and license QA. No OAuth or uploader code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SLUG = "vantage-sensitivity-sensitive-gifted-children"
SOURCE_SHA = "e264d2962b9028afc73463edcd2718b37539212762b0a72e35507d33dcb270ea"
PLAN_FILE = ROOT / "research/kesher-vantage-overview-full-private-20261109.json"
SOURCE_FILE = ROOT / "research/kesher-vantage-sensitivity-20261109.md"
SCENE_RE = re.compile(r"^images/(?:blog|generated/blog)/[a-z0-9][a-z0-9-]*\.(?:jpg|jpeg|png|webp)$")
SHA_RE = re.compile(r"^[a-f0-9]{64}$")
BANNED = (
    "פי עשר", "מגבר אוניברסלי", "עשרות אחוזים",
    "כל ילד רגיש מחונן",
)
FPS = 30
MIN_SCENES = 6
MAX_SCENES = 12


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for buf in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()


def run(args: list[str], *, cwd: Path | None = None, timeout: int = 900) -> str:
    done = subprocess.run(args, cwd=cwd, check=True, capture_output=True,
                          text=True, timeout=timeout)
    return done.stdout


def probe(path: Path) -> dict:
    return json.loads(run(["ffprobe", "-v", "error", "-show_streams",
                           "-show_format", "-of", "json", str(path)], timeout=40))


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def checked_regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"NONREGULAR_INPUT: {path}")


def validate_plan(plan: dict) -> list[dict]:
    checked_regular(SOURCE_FILE)
    research = SOURCE_FILE.read_text(encoding="utf-8")
    if SOURCE_SLUG not in research or SOURCE_SHA not in research:
        raise ValueError("RESEARCH_SOURCE_IDENTITY_CHANGED")
    if (plan.get("schema_version") != 1
            or plan.get("purpose") != "PRIVATE_FULL_OVERVIEW_QA_CANDIDATE"
            or plan.get("no_publication") is not True
            or plan.get("not_editorial_approval") is not True
            or plan.get("existing_public_overview_id") != "lnP5GltTLNk"
            or plan.get("sourceBinding") !=
                {"slug": SOURCE_SLUG, "contentSha256": SOURCE_SHA}):
        raise ValueError("PRIVATE_ONLY_SOURCE_IDENTITY_REQUIRED")
    story = plan.get("licensedPhotoStory")
    if not isinstance(story, dict) or story.get("sourceSlug") != SOURCE_SLUG or story.get("contentSha256") != SOURCE_SHA:
        raise ValueError("STORY_SOURCE_MISMATCH")
    scenes = story.get("scenes")
    if not isinstance(scenes, list) or not MIN_SCENES <= len(scenes) <= MAX_SCENES:
        raise ValueError("PHOTO_STORY_SCENE_COUNT_INVALID")
    unique: set[str] = set()
    for i, scene in enumerate(scenes):
        name = scene["assetPath"]
        if not SCENE_RE.fullmatch(name) or name in unique:
            raise ValueError(f"PHOTO_SCENE_PATH_OR_DUPLICATE: {i}")
        unique.add(name)
        p = ROOT / "public" / name
        checked_regular(p)
        expected = scene.get("assetSha256", "")
        if not SHA_RE.fullmatch(expected) or digest(p) != expected:
            raise ValueError(f"PHOTO_SCENE_HASH_MISMATCH: {i}")
        if not (isinstance(scene.get("altHebrew"), str)
                and re.search(r"[\u0590-\u05ff]", scene["altHebrew"])):
            raise ValueError(f"PHOTO_SCENE_HEBREW_ALT_REQUIRED: {i}")
        if not (isinstance(scene.get("licenseEvidenceUrl"), str)
                and scene["licenseEvidenceUrl"].startswith("https://")
                and scene.get("rightsStatus") not in ("approved", "QA_PASSED")):
            raise ValueError(f"PHOTO_SCENE_RIGHTS_HOLD_REQUIRED: {i}")
        script = scene.get("voiceText", "")
        if not isinstance(script, str) or len(script.split()) < 20 or any(x in script for x in BANNED):
            raise ValueError(f"PHOTO_SCENE_SCRIPT_INVALID: {i}")
    whole = " ".join(scene["voiceText"] for scene in scenes)
    if not all(part in whole for part in ("מייקל פלואס", "בלסקי", "בריונות", "בנים", "יותר מאלפיים", "אינה לבדה הוכחה")):
        raise ValueError("SCIENTIFIC_CAVEATS_MISSING")
    return scenes


def stage_images(scenes: list[dict]) -> list[dict]:
    evidence = []
    for scene in scenes:
        path = scene["assetPath"]
        src = ROOT / "public" / path
        target = ROOT / "remotion-kesher/public" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise ValueError("STAGED_IMAGE_SYMLINK")
        shutil.copyfile(src, target)
        if digest(target) != scene["assetSha256"]:
            raise ValueError("IMAGE_STAGING_CHECKSUM_FAILURE")
        evidence.append({"path": path, "sha256": scene["assetSha256"],
                         "rightsStatus": scene["rightsStatus"]})
    return evidence


def synthesize_licensed_hebrew(scenes: list[dict], output: Path) -> tuple[Path, list[int], dict]:
    from huggingface_hub import HfApi
    # Reuse the EXACT model/G2P revisions independently reviewed for the Short.
    approved_voice_sha = "95feb5d0cbfc8e5a95bffb067d03537cbf35be3e"
    approved_hebrew_g2p_sha = "679c56ca449d41873fb8ff7711ddf7563d28198f"
    hub = HfApi()
    v_model = hub.model_info("notmax123/BlueTTS2.5-onnx")
    g_model = hub.model_info("notmax123/RenikudPlus")
    if v_model.sha != approved_voice_sha or g_model.sha != approved_hebrew_g2p_sha:
        raise RuntimeError("LICENSED_VOICE_MODEL_REVISION_MOVED: refuse until rights re-reviewed")
    # Direct script execution sets sys.path to scripts/, not the repository root.
    # Import the reviewed sibling implementation deterministically in both modes.
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts import kesher_owner_vantage_short as voice
    # Existing, previously deployed MIT/Apache-2.0/CC-BY synthesis, not Edge Read Aloud.
    # Neither its fixed Short source identity nor its YouTube publication entry is invoked.
    voice.SCENES = [(f"Overview scene {i+1}", scene["voiceText"]) for i, scene in enumerate(scenes)]
    files, durations, provenance = voice.speak(output)
    # Do not archive hundreds of megabytes of downloaded public ONNX weights:
    # SHA-bound model provenance is recorded, while only generated WAVs are retained.
    weights_dir = output / "bluetts-model"
    if (weights_dir.is_dir() and not weights_dir.is_symlink()
            and weights_dir.resolve().is_relative_to(output.resolve())):
        shutil.rmtree(weights_dir)
    if len(files) != len(scenes) or len(durations) != len(scenes):
        raise RuntimeError("SPEECH_SEGMENT_COUNT_MISMATCH")
    waveforms = []
    ends = []
    total_samples = 0
    sample_rate = None
    for i, file in enumerate(files):
        signal, sr = sf.read(str(file), dtype="float32", always_2d=False)
        signal = np.asarray(signal, dtype=np.float32).reshape(-1)
        if signal.size < int(sr * 2.5) or not np.isfinite(signal).all():
            raise RuntimeError(f"SPEECH_SCENE_EMPTY_OR_NONFINITE: {i}")
        if np.max(np.abs(signal)) > 1.001 or np.sqrt(np.mean(signal ** 2)) < 0.002:
            raise RuntimeError(f"SPEECH_SCENE_INVALID_PEAK_OR_SILENCE: {i}")
        if sample_rate is None:
            sample_rate = sr
        if sr != sample_rate:
            raise RuntimeError("SPEECH_SAMPLE_RATE_MISMATCH")
        # Controlled natural transition; no hidden time-stretch or pitch change.
        tail = np.zeros(round(sr * 0.38), dtype=np.float32)
        waveforms.extend([signal, tail])
        total_samples += signal.size + tail.size
        end = round((total_samples / sample_rate) * FPS)
        ends.append(end)
    final = output / "overview-research-bounded-voice.wav"
    sf.write(str(final), np.concatenate(waveforms), sample_rate, subtype="PCM_16")
    for a, b in zip([0, *ends[:-1]], ends):
        if b - a < 4 * FPS:
            raise RuntimeError("NARRATION_SCENE_TOO_SHORT_FOR_NATURAL_VISUAL")
    speech_seconds = duration(final)
    if not 75 <= speech_seconds <= 150:
        raise RuntimeError(f"NARRATION_DURATION_OUTSIDE_PRIVATE_BOUNDS: {speech_seconds:.2f}")
    provenance["duration_seconds"] = speech_seconds
    provenance["wav_sha256"] = digest(final)
    provenance["source_audio"] = "newly synthesized from approved-research-bounded private draft"
    return final, ends, provenance


def visual_story_props(scenes: list[dict], ends: list[int], audio_source: str, plan: dict) -> dict:
    prev = 0
    photo_scenes = []
    for scene, end in zip(scenes, ends):
        photo_scenes.append({k: scene[k] for k in
                            ("assetPath", "assetSha256", "licenseEvidenceUrl", "altHebrew")})
        photo_scenes[-1].update(startFrame=prev, endFrame=end)
        prev = end
    return {
        "videoSrc": audio_source, "title": "", "hook": "",
        "sourceDurationInFrames": ends[-1],
        "beatLabels": [],
        "sourceBinding": plan["sourceBinding"],
        "licensedPhotoStory": {
            "sourceSlug": SOURCE_SLUG,
            "contentSha256": SOURCE_SHA,
            "scenes": photo_scenes,
        },
    }


def extract_review_frames(video: Path, output: Path, ends: list[int]) -> list[dict]:
    from PIL import Image, ImageDraw, ImageStat
    durations = []
    offsets = [0, *ends[:-1]]
    sheet = Image.new("RGB", (1280, ((len(ends)+1)//2)*210), "#f7f5ef")
    draw = ImageDraw.Draw(sheet)
    for i, (first, last) in enumerate(zip(offsets, ends)):
        t = ((first + last)/2)/FPS
        path = output / f"scene-{i+1:02d}-midpoint.png"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-ss", str(round(t, 3)), "-i", str(video),
             "-frames:v", "1", str(path)], timeout=90)
        checked_regular(path)
        img = Image.open(path).convert("RGB")
        if img.size != (1280,720):
            raise RuntimeError(f"SCENE_INVALID_DIMENSIONS_{i+1}")
        means = ImageStat.Stat(img.resize((64,36))).mean
        if max(means) < 17 or min(means) > 249:
            raise RuntimeError(f"SCENE_BLANK_FRAME_{i+1}")
        img.thumbnail((630,190))
        left=(i%2)*640
        top=(i//2)*210
        sheet.paste(img,(left,top))
        draw.text((left+8,top+190),f"Scene {i+1:02d}  |  {t:.1f}s",fill="#182a25")
        durations.append({"scene":i+1,"timestamp_seconds":round(t,2),
                          "frame_sha256":digest(path)})
    p=output/"overview-contact-sheet.jpg"
    sheet.save(p,quality=87,subsampling=0)
    return durations


def render(output: Path) -> dict:
    checked_regular(PLAN_FILE)
    plan=json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    scenes=validate_plan(plan)
    output.mkdir(parents=True,exist_ok=False)
    assets=stage_images(scenes)
    audio,ends,voice_provenance=synthesize_licensed_hebrew(scenes,output)
    seconds=ends[-1]/FPS
    base=ROOT/"remotion-kesher/public/vantage-private-licensed-voice-base.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y",
         "-f","lavfi","-i","color=c=#132b29:s=1280x720:r=30",
         "-i",str(audio),"-t",str(seconds),"-c:v","libx264",
         "-preset","veryfast","-crf","29","-pix_fmt","yuv420p",
         "-c:a","aac","-b:a","160k","-movflags","+faststart",
         str(base)],timeout=360)
    props=visual_story_props(scenes,ends,base.name,plan)
    p=output/"full-private-props.json"
    p.write_text(json.dumps(props,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    binary=ROOT/"remotion-kesher/node_modules/.bin/remotion"
    if not binary.is_file() or not binary.resolve().is_relative_to((ROOT/"remotion-kesher/node_modules").resolve()):
        raise RuntimeError("PRIVATE_REMOTION_BINARY_MISSING_OR_UNSAFE")
    movie=output/"vantage-overview-full-private-heb.mp4"
    run([str(binary),"render","src/index.ts","KesherVideo",str(movie),
         "--props",str(p),"--codec=h264","--crf=23",
         "--concurrency=2","--log=error"],
        cwd=ROOT/"remotion-kesher",timeout=2100)
    checked_regular(movie)
    media=probe(movie)
    visual=next((s for s in media["streams"] if s["codec_type"]=="video"),None)
    sound=next((s for s in media["streams"] if s["codec_type"]=="audio"),None)
    if not visual or not sound or visual["codec_name"]!="h264" or sound["codec_name"]!="aac":
        raise RuntimeError("PRIVATE_FINAL_H264_AAC_REQUIRED")
    if (int(visual["width"]),int(visual["height"]))!=(1280,720):
        raise RuntimeError("PRIVATE_FINAL_DIMENSION_MISMATCH")
    actual=float(media["format"]["duration"])
    if abs(actual-duration(audio))>0.7:
        raise RuntimeError(f"PRIVATE_FINAL_AUDIO_SYNC_DELTA: {actual:.3f}")
    # Full-file decode catches corrupt segments, not subjective human listening.
    run(["ffmpeg","-v","error","-i",str(movie),"-f","null","-"],timeout=300)
    frame_evidence=extract_review_frames(movie,output,ends)
    transcript="\n".join(scene["voiceText"] for scene in scenes)+"\n"
    (output/"exact-hebrew-script.txt").write_text(transcript,encoding="utf-8")
    result={
        "status":"PRIVATE_FULL_OVERVIEW_RENDERED_NOT_PUBLISHED",
        "source_slug":SOURCE_SLUG,
        "source_sha256":SOURCE_SHA,
        "existing_public_video_id":"lnP5GltTLNk",
        "new_video_id":None,"youtube_uploaded":False,
        "full_private_movie_sha256":digest(movie),
        "full_private_audio_wav_sha256":digest(audio),
        "full_private_script_sha256":digest(output/"exact-hebrew-script.txt"),
        "full_private_duration_seconds":round(actual,3),
        "audio_duration_seconds":round(duration(audio),3),
        "target_duration_seconds":[90,130],
        "duration_target_met":90<=actual<=130,
        "resolution":"1280x720","codecs":"H.264/AAC",
        "scene_count":len(scenes),"scene_ends_frames":ends,
        "audio_engine":"BlueTTS2.5-onnx MIT + RenikudPlus Apache-2.0, CC-BY speaker reference",
        "voice_provenance":voice_provenance,
        "assets":assets,"visual_frame_evidence":frame_evidence,
        "rights_status":"QUALITY_HOLD image specific licensing pending",
        "semantic_review_status":"PENDING independent exact audio validation and source research review",
        "subjective_audition_status":"PENDING",
        "publication_status":"NOT_AUTHORIZED_PRIVATE_QA_ONLY",
        "autonomous_clean_cycle_counted":False,
    }
    (output/"manifest.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,required=True)
    render(ap.parse_args().output)
