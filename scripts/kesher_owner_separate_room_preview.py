#!/usr/bin/env python3
"""Exact-source private OWNER preview; no upload or external content generator."""
from __future__ import annotations
import argparse, json, re, subprocess
from pathlib import Path
from scripts.kesher_daily_pipeline import clean_article_html, source_metadata
from scripts.kesher_owner_positivity_preview import (
    sha_file, sha_bytes, encode_scene, join_scenes, review_frames,
    verify_video, MODEL_SHA, G2P_SHA,
)
ROOT = Path(__file__).resolve().parents[1]
SLUG = "transition-to-separate-room"
SOURCE_SHA = "4751cfeae272ce8d42e8311236d3bbacf44e94cd99b571db6b8544b103bfe8d0"
BODY_SHA = "9df3fef6d555e3d5efa8de74cc865dedbe9fdceade297611054623dbd18d0a52"
PLAN_SHA = "c02d9165667e9121cb8d49a1f18b5177c1dd7d46a2e4f397496b148b31707d81"
HERO_SHA = "f3efb6c10a6d5ca762f0ea2e855ed0ef2afd26ad90af56afa01cbff44c32c86d"
ARTICLE = "https://kesher.saharoni.com/blog/" + SLUG
PLAN = ROOT / "research/kesher-separate-room-media-20261110.json"
PHOTOS = ROOT / "research/kesher-separate-room-photo-provenance.json"
KINDS = ("overview", "short")
SIZES = {"overview": (1280, 720), "short": (1080, 1920)}
COUNTS = {"overview": 6, "short": 4}
LICENSES = {
    "Pexels": "https://www.pexels.com/legal-pages/license",
    "Adobe Firefly": "https://helpx.adobe.com/firefly/web/get-started/learn-the-basics/adobe-firefly-faq.html",
}
def source_check(*, public=False):
    from PIL import Image
    if sha_file(PLAN) != PLAN_SHA:
        raise ValueError("EXACT_SCRIPT_PLAN_CHANGED")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    if (plan["source_slug"], plan["content_sha256"], plan["canonical_content_sha256"], plan["article_body_sha256"]) != (SLUG, SOURCE_SHA, SOURCE_SHA, BODY_SHA):
        raise ValueError("SCRIPT_SOURCE_IDENTITY_CHANGED")
    scripts = plan["scripts"]
    if set(scripts) != set(KINDS):
        raise ValueError("SCRIPT_KIND_MISMATCH")
    for kind in KINDS:
        text = " ".join(scripts[kind])
        if len(scripts[kind]) != COUNTS[kind] or re.search(r"[A-Za-z]", text) or "לפחות עד גיל חצי שנה" not in text or "עדיף עד גיל שנה" not in text or "הקישור בתיאור" not in text:
            raise ValueError("SCRIPT_LANGUAGE_OR_SAFETY")
    posts = json.loads((ROOT / "src/data/postsRecent.json").read_text(encoding="utf-8"))
    rows = [p for p in posts if p.get("slug") == SLUG]
    if len(rows) != 1 or source_metadata(rows[0])["content_sha256"] != SOURCE_SHA or sha_bytes(clean_article_html(rows[0]["content"]).encode()) != BODY_SHA:
        raise ValueError("ARTICLE_SOURCE_IDENTITY_CHANGED")
    provenance = json.loads(PHOTOS.read_text(encoding="utf-8"))
    if (provenance["source_slug"], provenance["content_sha256"], provenance["canonical_content_sha256"], provenance["article_body_sha256"], provenance["plan_sha256"], provenance["article_hero_sha256"]) != (SLUG, SOURCE_SHA, SOURCE_SHA, BODY_SHA, PLAN_SHA, HERO_SHA):
        raise ValueError("PHOTO_SOURCE_IDENTITY_CHANGED")
    dedup = provenance["dedup_evidence"]
    if (dedup["run_id"], dedup["head_sha"], dedup["workflow_id"], dedup["source_slug"], dedup["content_sha256"]) != (42920640111, "f0c31debb380540e16ddd6a87499793f67e241ac", 349292838, SLUG, SOURCE_SHA) or dedup["complete"] is not True or dedup["candidates"] != [] or dedup["no_youtube_mutation"] is not True:
        raise ValueError("EXACT_DEDUP_REQUIRED")
    images = provenance["images"]
    expected = [f"{kind}-{i}" for kind in KINDS for i in range(COUNTS[kind])]
    if [x["scene"] for x in images] != expected or len({x["sha256"] for x in images}) != len(expected):
        raise ValueError("PHOTO_SCENE_IDENTITY_CHANGED")
    for item in images:
        kind = item["scene"].split("-")[0]
        path = ROOT / item["path"]
        if (not path.is_file() or path.is_symlink() or not str(path.resolve()).startswith(str(ROOT / "public/images/blog") + "/")
            or sha_file(path) != item["sha256"] or item["generated_for"] != SLUG or item.get("commercial_use_permitted") is not True
            or item.get("license_url") != LICENSES.get(item.get("provider")) or not item.get("visual_review") or not item.get("credit")):
            raise ValueError("PHOTO_RIGHTS_OR_BYTES_MISMATCH")
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            if im.size != SIZES[kind] or list(im.size) != item["dimensions"]:
                raise ValueError("PHOTO_DIMENSION_MISMATCH")
    if public:
        import requests
        r = requests.get(ARTICLE, timeout=30)
        m = requests.get("https://kesher.saharoni.com/.well-known/kesher-publication.json", timeout=30)
        if r.status_code != 200 or m.status_code != 200 or f'rel="canonical" href="{ARTICLE}"' not in r.text or f'<meta name="kesher:content-sha256" content="{SOURCE_SHA}">' not in r.text:
            raise ValueError("LIVE_ARTICLE_IDENTITY_MISMATCH")
        row = m.json()["articles"].get(SLUG)
        if not row or row["identity"]["content_sha256"] != SOURCE_SHA or row["canonical_url"] != ARTICLE or row["html_sha256"] != sha_bytes(r.content) or row["hero"]["sha256"] != HERO_SHA:
            raise ValueError("LIVE_MANIFEST_IDENTITY_MISMATCH")
        hero = requests.get("https://kesher.saharoni.com" + row["hero"]["path"], timeout=30)
        if hero.status_code != 200 or sha_bytes(hero.content) != HERO_SHA:
            raise ValueError("LIVE_HERO_IDENTITY_MISMATCH")
    return scripts, provenance

def preview(out):
    scripts, provenance = source_check(public=True)
    if out.exists():
        raise ValueError("PREVIEW_EXISTS")
    out.mkdir(parents=True)
    from scripts import kesher_owner_vantage_short as voice
    voice.SCENES = [(f"{kind}-{i}", text) for kind in KINDS for i, text in enumerate(scripts[kind])]
    voices, durations, info = voice.speak(out)
    if len(voices) != 10 or info["model_revision"] != MODEL_SHA or info["g2p_revision"] != G2P_SHA or info["weights_license"] != "MIT" or info["reference_license"] != "CC BY 4.0" or info["g2p_license"] != "Apache-2.0":
        raise ValueError("VOICE_RIGHTS_OR_REVISION_CHANGED")
    offset = 0
    for kind in KINDS:
        loc = out / kind
        loc.mkdir()
        count = COUNTS[kind]
        voicepaths = voices[offset:offset+count]
        secs = durations[offset:offset+count]
        photos = provenance["images"][offset:offset+count]
        offset += count
        segments = []
        for i, item in enumerate(photos):
            part = loc / f"segment-{i}.mp4"
            encode_scene(ROOT / item["path"], voicepaths[i], part, kind, secs[i] + 0.10, i % 2 == 1)
            segments.append(part)
        video = out / f"{kind}.mp4"
        join_scenes(segments, video)
        wav = out / f"{kind}-review-voice.wav"
        subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", str(video), "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)], check=True)
        media = verify_video(video, kind)
        frames, contact = review_frames(video, out, kind)
        manifest = {
            "source_slug": SLUG, "content_sha256": SOURCE_SHA, "canonical_content_sha256": SOURCE_SHA, "article_body_sha256": BODY_SHA,
            "kind": kind, "media_item_id": f"owner-{kind}-20261111-{SOURCE_SHA[:12]}",
            "source_file": str(PLAN.relative_to(ROOT)), "source_file_sha256": sha_file(PLAN),
            "script_segments": scripts[kind], "script_sha256": sha_bytes("\n".join(scripts[kind]).encode()),
            "visual_sources": photos, "voice_provenance": info,
            "voice_model": "BlueTTS2.5-onnx:libri_female_6147", "video_sha256": sha_file(video),
            "audio_sha256": sha_file(wav), "audio_review_source": "decoded_final_mp4_audio",
            "contact_sha256": sha_file(contact), "frame_sha256": [sha_file(x) for x in frames],
            "media": media, "composition": "native_full_frame_9_16_no_padding" if kind == "short" else "full_frame_16_9",
            "owner_editorial_qa": "PENDING_GENUINE_INDEPENDENT_REVIEW", "uploaded": False, "public": False,
        }
        (out / f"{kind}-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("OWNER_PRIVATE_PREVIEW_READY", kind, manifest["video_sha256"], media, flush=True)

def transcribe(out):
    from faster_whisper import WhisperModel
    from scripts.kesher_owner_positivity_asr import similarity
    model = WhisperModel("small", device="cpu", compute_type="int8", download_root=str(out / "asr-model-cache"))
    report = {"source_slug": SLUG, "content_sha256": SOURCE_SHA, "canonical_content_sha256": SOURCE_SHA, "article_body_sha256": BODY_SHA,
              "engine": "faster-whisper==1.2.1 / small Hebrew", "audio_source": "decoded_final_mp4_audio",
              "review": "PENDING_OWNER_EDITORIAL_CONFIRMATION", "media": {}}
    for kind in KINDS:
        m = json.loads((out / f"{kind}-manifest.json").read_text())
        wav = out / f"{kind}-review-voice.wav"
        if (m["source_slug"], m["content_sha256"], m["canonical_content_sha256"], m["article_body_sha256"]) != (SLUG, SOURCE_SHA, SOURCE_SHA, BODY_SHA) or sha_file(wav) != m["audio_sha256"] or sha_file(out / f"{kind}.mp4") != m["video_sha256"] or m["public"] is not False:
            raise ValueError("ASR_IDENTITY_MISMATCH")
        segments, details = model.transcribe(str(wav), language="he", beam_size=5, condition_on_previous_text=False, vad_filter=False)
        text = " ".join(x.text.strip() for x in segments).strip()
        if len(re.findall(r"[\u0590-\u05ff]", text)) < 60:
            raise ValueError("ASR_TOO_LITTLE_HEBREW")
        p = out / f"{kind}-asr.txt"
        p.write_text(text + "\n", encoding="utf-8")
        report["media"][kind] = {"audio_sha256": m["audio_sha256"], "transcript_sha256": sha_file(p),
                                 "script_sha256": m["script_sha256"], "script_similarity": similarity(text, " ".join(m["script_segments"])),
                                 "language": details.language, "editorial_decision": "QA_PENDING_REVIEW", "human_listening": False}
    (out / "asr-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ASR_EVIDENCE_READY_NO_PUBLICATION", flush=True)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("operation", choices=["preflight", "preview", "asr"])
    p.add_argument("--source-sha", required=True)
    p.add_argument("--output", type=Path, default=Path("owner-separate-room-media-output"))
    a = p.parse_args()
    if a.source_sha != SOURCE_SHA:
        raise SystemExit("EXACT_SOURCE_SHA_REQUIRED")
    if a.operation == "preflight":
        source_check(public=True)
        print("SOURCE_PREFLIGHT_OK", SLUG, SOURCE_SHA)
    elif a.operation == "preview":
        preview(a.output)
    else:
        transcribe(a.output)
