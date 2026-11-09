#!/usr/bin/env python3
"""One-source, one-time OWNER media repair. No legacy content agent or bridge."""
import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

SLUG = "vantage-sensitivity-sensitive-gifted-children"
SOURCE_SHA = "e264d2962b9028afc73463edcd2718b37539212762b0a72e35507d33dcb270ea"
SHORT_ITEM_ID = "video-20261109-094900-e264d2962b"
OVERVIEW_VIDEO_ID = "lnP5GltTLNk"
OVERVIEW_ITEM_ID = "video-20261109-085219-e264d2962b"
CHANNEL_ID = "UCx5fEFvdVf28HLAR2dFW64Q"
ARTICLE = "https://kesher.saharoni.com/blog/" + SLUG
VOICE = "BlueTTS2.5-onnx:libri_female_6147"
TITLE = "הילד רגיש במיוחד? כך סביבה תומכת יכולה לעזור | שירה סהרוני #Shorts"
REPO = "yanivsa/kesher-website"
SCENES = [
    ("לא כל רגישות היא חולשה",
     "תגית בבגד מגרדת. רעש בכיתה מציף. והערה קטנה נשארת בלב. זו לא בהכרח חולשה."),
    ("מהי רגישות יתרון?",
     "מייקל פלואס וג׳יי בלסקי הציעו רעיון שנקרא רגישות יתרון: יש אנשים שעשויים להפיק יותר תועלת מחוויות חיוביות ותומכות."),
    ("המחקר אינו מבטיח מחוננות",
     "במחקר מבוקר עם יותר מאלפיים תלמידים, ההשפעה של תוכנית נגד בריונות בלטה במיוחד אצל בנים בעלי רגישות גבוהה. זו לא הבטחה ליתרון בכל תחום."),
    ("תיקוף רגש עם גבול ברור",
     "במקום לומר תפסיק להיות רגיש, נסו לומר: אני רואה שהרעש קשה לך. בוא נמצא מקום שקט. ואת הגבול נשאיר ברור."),
    ("הכירו מה עוזר לילד",
     "רגישות היא לא כוח על, וגם לא תקלה. עזרו לילד לגלות מה טוב לו. המאמר המלא באתר קשר."),
]
PROHIBITED = ("פי עשר", "יתרון התפתחותי עצום", "מגבר אוניברסלי", "עשרות אחוזים", "כל ילד רגיש מחונן")


def run(*args, quiet=False):
    p = subprocess.run(args, check=True, capture_output=quiet, text=quiet, timeout=600)
    return p.stdout if quiet else ""


def duration(path):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=nokey=1:noprint_wrappers=1", str(path), quiet=True).strip())


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def preflight():
    article = Path("research/kesher-vantage-sensitivity-20261109.md").read_text(encoding="utf-8")
    assert SLUG in article and SOURCE_SHA in article, "Source identity changed"
    assert Path("public/images/blog/vantage-sensitivity-parenting-hero.jpg").is_file(), "Original source image missing"
    text = "\n".join(row[1] for row in SCENES)
    assert all(value not in text for value in PROHIBITED), "Prohibited overclaim"
    assert "יותר מאלפיים" in text and "בנים" in text, "RCT scope missing"


def draw_slide(number, headline, dest):
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    from PIL import features
    assert features.check("raqm"), "Hebrew RTL layout requires RAQM"
    W, H = 1080, 1920
    canvas = Image.new("RGB", (W, H), "#09343A")
    d = ImageDraw.Draw(canvas)
    photo = Image.open("public/images/blog/vantage-sensitivity-parenting-hero.jpg").convert("RGB")
    photo = ImageOps.fit(photo, (900, 690), method=Image.Resampling.LANCZOS)
    canvas.paste(photo, (90, 430))
    d.rounded_rectangle((62, 1075, 1018, 1624), radius=46, fill="#FAF6ED")
    d.rounded_rectangle((68, 132, 1010, 345), radius=34, fill="#0C404A")
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_title = ImageFont.truetype(font_path, 61)
    font_caption = ImageFont.truetype(font_path, 64)
    font_small = ImageFont.truetype(font_path, 35)
    d.text((960, 192), "קשר | הדרכת הורים", font=font_title, fill="#FDF9EF",
           anchor="ra", direction="rtl")
    d.text((940, 1180), headline, font=font_caption, fill="#124C53",
           anchor="ra", direction="rtl", stroke_width=0)
    d.text((940, 1385), "רגישות יתרון • מידע מבוסס מחקר", font=font_small,
           fill="#355B5D", anchor="ra", direction="rtl")
    d.text((940, 1530), "המאמר המלא: kesher.saharoni.com", font=font_small,
           fill="#134A52", anchor="ra", direction="rtl")
    d.text((975, 1708), f"{number:02d} / {len(SCENES):02d}", font=font_small,
           fill="#D9E7E4", anchor="ra")
    # Exact placements are fixed; headlines must fit within the isolated panel.
    extent = d.textbbox((940, 1180), headline, font=font_caption, anchor="ra", direction="rtl")
    assert extent[0] > 95 and extent[2] < 975 and extent[3] < 1320, f"Text overflow: {headline}"
    canvas.save(dest)


def _speech_chunks(script):
    """Keep the licensed model below its per-utterance duration limit."""
    import re
    phrases = re.split(r"(?<=[.!?])\s+|(?<=:)\s+|(?<=,)\s+", script)
    chunks = []
    for phrase in phrases:
        if not phrase.strip():
            continue
        words = phrase.split()
        # 12 words or less prevents the ~16s ONNX duration saturation.
        for offset in range(0, len(words), 12):
            chunk = " ".join(words[offset:offset + 12]).strip()
            if chunk:
                chunks.append(chunk)
    return chunks


def speak(dirpath):
    """Synthesize locally with MIT-licensed Hebrew ONNX weights; never Edge Read Aloud."""
    import numpy as np
    import soundfile as sf
    from blue_onnx import BlueTTS
    from huggingface_hub import HfApi, snapshot_download

    model_info = HfApi().model_info("notmax123/BlueTTS2.5-onnx")
    assert model_info.sha and len(model_info.sha) == 40, "Unpinned Hebrew TTS model revision"
    assert model_info.card_data and str(model_info.card_data.license).lower() == "mit", "Model weights are not MIT"
    model_rev = model_info.sha
    model_dir = Path(snapshot_download(
        repo_id="notmax123/BlueTTS2.5-onnx",
        revision=model_rev,
        local_dir=str(dirpath / "bluetts-model"),
        allow_patterns=["*.onnx", "*.npz", "*.json", "voices/*.json"],
        max_workers=4,
    ))
    style = model_dir / "voices" / "libri_female_6147.json"
    assert style.is_file(), "Licensed LibriTTS-R voice style missing"
    tts = BlueTTS(onnx_dir=str(model_dir), style_json=str(style))
    paths, durations = [], []
    for idx, (_headline, script) in enumerate(SCENES):
        chunks = _speech_chunks(script)
        assert chunks, "Missing scene narration"
        parts = []
        sample_rate = None
        for phrase in chunks:
            arr, sr = tts.synthesize(phrase, lang="he")
            wave = np.asarray(arr, dtype=np.float32).reshape(-1)
            assert len(wave) >= 3500 and np.isfinite(wave).all(), "Invalid Hebrew speech output"
            assert float(np.max(np.abs(wave))) < 1.001, "Out-of-range audio peaks"
            if sample_rate is None:
                sample_rate = int(sr)
            assert sr == sample_rate
            parts.extend((wave, np.zeros(int(sr * 0.075), dtype=np.float32)))
        path = dirpath / f"voice-{idx:02d}.wav"
        sf.write(str(path), np.concatenate(parts), sample_rate, subtype="PCM_16")
        sec = duration(path)
        assert 2 < sec < 55, "Invalid speech scene duration"
        durations.append(sec)
        paths.append(path)
    license_provenance = {
        "model_repo": "notmax123/BlueTTS2.5-onnx",
        "model_revision": model_rev,
        "weights_license": "MIT",
        "weights_license_url": "https://huggingface.co/notmax123/BlueTTS2.5-onnx",
        "voice_preset": "libri_female_6147",
        "voice_reference_corpus": "LibriTTS-R train-clean-100",
        "reference_license": "CC BY 4.0",
        "reference_license_url": "https://www.openslr.org/141/",
        "voice_reference_attribution": "LibriTTS-R / Google LLC; speaker 6147",
        "g2p_model": "notmax123/RenikudPlus",
        "g2p_license_url": "https://huggingface.co/notmax123/RenikudPlus",
    }
    print("OWNER_LICENSED_TTS model=" + license_provenance["model_repo"] + " revision=" + model_rev)
    return paths, durations, license_provenance


def ffconcat(dest, files, lengths=None):
    lines = ["ffconcat version 1.0"]
    for idx, file in enumerate(files):
        lines.append("file '" + str(file.resolve()) + "'")
        if lengths is not None:
            lines.append(f"duration {lengths[idx]:.5f}")
    if lengths is not None:
        lines.append("file '" + str(files[-1].resolve()) + "'")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def media_verify(video):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
                       check=True, capture_output=True, text=True, timeout=120)
    data = json.loads(p.stdout)
    streams = data["streams"]
    visual = next(s for s in streams if s["codec_type"] == "video")
    audio = next(s for s in streams if s["codec_type"] == "audio")
    assert (int(visual["width"]), int(visual["height"])) == (1080, 1920), "Not native portrait 9:16"
    assert visual["codec_name"] == "h264" and audio["codec_name"] == "aac", "Codecs not approved"
    seconds = float(data["format"]["duration"])
    assert 35 < seconds < 119, "Invalid short length"
    run("ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-f", "null", "-")
    return {"width": 1080, "height": 1920, "duration": round(seconds, 3),
            "video_codec": "h264", "audio_codec": "aac"}


def preview():
    preflight()
    from PIL import Image
    out = Path("owner-vantage-short-output")
    out.mkdir(exist_ok=True)
    voices, seconds, licensed_voice = speak(out)
    slides = []
    for idx, (headline, _script) in enumerate(SCENES):
        image = out / f"frame-{idx:02d}.png"
        draw_slide(idx + 1, headline, image)
        slides.append(image)
    ffconcat(out / "voice.ffconcat", voices)
    run("ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "concat", "-safe", "0",
        "-i", str(out / "voice.ffconcat"), "-ar", "48000", "-ac", "1", "-c:a",
        "pcm_s16le", str(out / "review-voice.wav"))
    full_seconds = duration(out / "review-voice.wav")
    ffconcat(out / "frames.ffconcat", slides, seconds)
    run("ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "concat", "-safe", "0",
        "-i", str(out / "frames.ffconcat"), "-i", str(out / "review-voice.wav"),
        "-t", f"{full_seconds:.4f}", "-r", "15", "-c:v", "libx264", "-preset",
        "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a",
        "128k", "-movflags", "+faststart", str(out / "short.mp4"))
    meta = media_verify(out / "short.mp4")
    assert abs(meta["duration"] - full_seconds) < 0.75, "Narration/video time mismatch"
    sheet = Image.new("RGB", (1350, 480), "#0C404A")
    for idx, item in enumerate(slides):
        frame = Image.open(item).convert("RGB")
        frame.thumbnail((270, 480))
        sheet.paste(frame, (idx * 270, 0))
    sheet.save(out / "visual-contact-sheet.jpg", quality=87)
    manifest = {
        "source_slug": SLUG,
        "source_sha256": SOURCE_SHA,
        "short_item_id": SHORT_ITEM_ID,
        "overview_video_id": OVERVIEW_VIDEO_ID,
        "overview_item_id": OVERVIEW_ITEM_ID,
        "voice": VOICE,
        "voice_provenance": licensed_voice,
        "script_segments": [script for _label, script in SCENES],
        "script_sha256": hashlib.sha256("\n".join(script for _, script in SCENES).encode()).hexdigest(),
        "media": meta,
        "video_sha256": sha(out / "short.mp4"),
        "audio_sha256": sha(out / "review-voice.wav"),
        "visual_contact_sha256": sha(out / "visual-contact-sheet.jpg"),
        "audio_review": "PENDING_INDEPENDENT_REVIEW",
        "visual_review": "PENDING_INDEPENDENT_REVIEW",
        "is_public": False,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OWNER_PREVIEW_READY item=" + SHORT_ITEM_ID + " sha256=" + manifest["video_sha256"]
          + " voice_review=pending visual_review=pending")


def youtube_client():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    scopes = ["https://www.googleapis.com/auth/youtube.upload",
              "https://www.googleapis.com/auth/youtube.readonly"]
    keys = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    if any(not os.environ.get(k) for k in keys):
        raise RuntimeError("Missing authorized GitHub YouTube OAuth secret")
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=scopes)
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def already_published(youtube, uploads_playlist):
    ids = []
    token = None
    for _page in range(4):
        response = youtube.playlistItems().list(part="contentDetails", playlistId=uploads_playlist,
                                               maxResults=50, pageToken=token).execute()
        ids.extend(x["contentDetails"]["videoId"] for x in response.get("items", []))
        token = response.get("nextPageToken")
        if not token:
            break
    for index in range(0, len(ids), 50):
        payload = youtube.videos().list(part="snippet,status,processingDetails",
                                        id=",".join(ids[index:index + 50])).execute()
        for item in payload.get("items", []):
            meta = item.get("snippet", {})
            desc = meta.get("description") or ""
            if (meta.get("channelId") == CHANNEL_ID
                    and SLUG in desc and SOURCE_SHA in desc
                    and "KESHER_OWNER_SHORT_ITEM=" + SHORT_ITEM_ID in desc):
                return item
    return None


def verify_voice_license(approve, manifest):
    """Fail closed on the exact pretrained voice provenance and CC-BY attribution."""
    rights = approve.get("voice_license")
    provenance = manifest.get("voice_provenance")
    assert isinstance(rights, dict) and isinstance(provenance, dict), \
        "VOICE_LICENSE_NOT_VERIFIED: missing exact license evidence"
    expected = {
        "voice_source": VOICE,
        "model_repo": "notmax123/BlueTTS2.5-onnx",
        "model_license": "MIT",
        "license_evidence_url": "https://huggingface.co/notmax123/BlueTTS2.5-onnx",
        "voice_reference_corpus": "LibriTTS-R train-clean-100",
        "reference_license": "CC BY 4.0",
        "reference_license_url": "https://www.openslr.org/141/",
    }
    assert all(rights.get(k) == v for k, v in expected.items()), \
        "VOICE_LICENSE_NOT_VERIFIED: source or evidence mismatch"
    assert rights.get("commercial_use_permitted") is True, \
        "VOICE_LICENSE_NOT_VERIFIED: commercial-use flag missing"
    assert rights.get("attribution_in_description") is True, \
        "VOICE_LICENSE_NOT_VERIFIED: CC-BY attribution required"
    assert (manifest.get("voice") == VOICE
            and provenance.get("model_repo") == expected["model_repo"]
            and provenance.get("weights_license") == expected["model_license"]
            and provenance.get("weights_license_url") == expected["license_evidence_url"]
            and provenance.get("reference_license") == expected["reference_license"]
            and provenance.get("reference_license_url") == expected["reference_license_url"]
            and provenance.get("voice_preset") == "libri_female_6147"
            and isinstance(provenance.get("model_revision"), str)
            and len(provenance["model_revision"]) == 40), \
        "VOICE_LICENSE_NOT_VERIFIED: reviewed rendering provenance mismatch"


def validate_approved_bundle():
    preflight()
    out = Path("owner-vantage-short-output")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    approve = json.loads(Path("research/kesher-vantage-short-approval.json").read_text(encoding="utf-8"))
    checks = ["audio_review_pass", "visual_review_pass", "semantic_review_pass"]
    assert all(approve.get(k) is True for k in checks), "Real OWNER QA not explicitly approved"
    verify_voice_license(approve, manifest)
    assert (approve["video_sha256"] == manifest["video_sha256"]
            and manifest["video_sha256"] == sha(out / "short.mp4")), "Video changed after QA"
    assert approve["source_sha256"] == SOURCE_SHA == manifest["source_sha256"]
    assert approve["source_slug"] == SLUG == manifest["source_slug"]
    assert approve["short_item_id"] == SHORT_ITEM_ID == manifest["short_item_id"]
    assert manifest["overview_video_id"] == OVERVIEW_VIDEO_ID
    assert sha(out / "review-voice.wav") == manifest["audio_sha256"]
    assert sha(out / "visual-contact-sheet.jpg") == manifest["visual_contact_sha256"]
    assert approve.get("evidence") and approve.get("approved_by") == "OWNER"
    media_verify(out / "short.mp4")
    return out, manifest


def publish():
    out, manifest = validate_approved_bundle()
    import requests
    from googleapiclient.http import MediaFileUpload
    page = requests.get(ARTICLE, timeout=30, headers={"User-Agent": "Kesher-Owner-QA/1.0"})
    assert page.status_code == 200 and SLUG in page.text, "Public article not available"
    assert "canonical" in page.text.lower() and ARTICLE in page.text, "Article canonical check failed"
    yt = youtube_client()
    channels = yt.channels().list(part="id,contentDetails", mine=True).execute().get("items", [])
    assert len(channels) == 1 and channels[0]["id"] == CHANNEL_ID, "Wrong YouTube channel"
    uploads = channels[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    found = already_published(yt, uploads)
    if found:
        vid = found["id"]
        print("OWNER_SHORT_ALREADY_EXISTS https://www.youtube.com/shorts/" + vid)
    else:
        description = ("איך עוזרים לילד רגיש בלי הבטחות מופרזות?\n\n"
                       + ARTICLE + "\n\nהסרטון מבוסס על מחקרים המפורטים במאמר.\n"
                       + "KESHER_OWNER_SHORT_ITEM=" + SHORT_ITEM_ID + "\n"
                       + "source_slug=" + SLUG + "\n"
                       + "content_sha256=" + SOURCE_SHA + "\n"
                       + "overview=https://www.youtube.com/watch?v=" + OVERVIEW_VIDEO_ID
                       + "\nקריינות סינתטית: BlueTTS 2.5 (משקולות MIT), LibriTTS-R / Google LLC, דובר/ת 6147 (CC BY 4.0).\nhttps://huggingface.co/notmax123/BlueTTS2.5-onnx\nhttps://www.openslr.org/141/"
                       + "\n#הדרכתהורים #ילדיםרגישים #Shorts")
        body = {"snippet": {"title": TITLE, "description": description, "categoryId": "22",
                            "tags": ["רגישות יתרון", "הדרכת הורים", "שירה סהרוני"],
                            "defaultLanguage": "he", "defaultAudioLanguage": "he"},
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
        upload = yt.videos().insert(part="snippet,status", body=body,
                                   media_body=MediaFileUpload(str(out / "short.mp4"),
                                                              mimetype="video/mp4", resumable=True))
        response = None
        while response is None:
            _status, response = upload.next_chunk()
        vid = response["id"]
        print("OWNER_SHORT_UPLOADED_ONE_TIME id=" + vid)
    verified = False
    for _ in range(18):
        check = yt.videos().list(part="snippet,status,processingDetails", id=vid).execute().get("items", [])
        if check:
            item = check[0]
            status = item.get("status", {})
            proc = (item.get("processingDetails") or {}).get("processingStatus")
            if (status.get("privacyStatus") == "public"
                    and item.get("snippet", {}).get("channelId") == CHANNEL_ID
                    and proc == "succeeded"):
                verified = True
                break
            if proc == "failed":
                raise RuntimeError("YouTube media processing failed")
        time.sleep(10)
    if not verified:
        raise RuntimeError("YouTube upload exists, public processing has not succeeded; do not reupload")
    short_url = "https://www.youtube.com/shorts/" + vid
    print("OWNER_SHORT_PUBLIC_VERIFIED " + short_url)
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        comment = ("OWNER DIRECT VERIFIED PUBLIC VANTAGE SHORT: " + short_url
                   + "\nArticle: " + ARTICLE
                   + "\nVideo: https://www.youtube.com/watch?v=" + OVERVIEW_VIDEO_ID
                   + "\nShort: " + short_url
                   + "\nsource_slug=" + SLUG + " content_sha256=" + SOURCE_SHA
                   + "\nshort_item_id=" + SHORT_ITEM_ID
                   + "\nmedia_sha256=" + manifest["video_sha256"]
                   + "\nprocessing=succeeded privacy=public channel=" + CHANNEL_ID
                   + "\nClean-cycle assessment: assisted repair, not in 3/3 streak.")
        res = requests.post("https://api.github.com/repos/" + REPO + "/issues/1210/comments",
                            headers={"Authorization": "Bearer " + token,
                                     "Accept": "application/vnd.github+json"},
                            json={"body": comment}, timeout=20)
        if res.status_code not in (200, 201):
            print("WARNING issue update failed", res.status_code)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("operation", choices=["preview", "publish", "preflight"])
    ap.add_argument("--source-sha", required=True)
    args = ap.parse_args()
    if args.source_sha != SOURCE_SHA:
        raise SystemExit("Exact source SHA mismatch; refuse")
    if args.operation == "preview":
        preview()
    elif args.operation == "publish":
        publish()
    else:
        preflight()
        print("OWNER_SOURCE_PREFLIGHT_OK " + SLUG + " " + SOURCE_SHA)
