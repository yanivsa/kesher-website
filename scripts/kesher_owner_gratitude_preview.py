#!/usr/bin/env python3
"""Direct OWNER one-day KESHER gratitude source-bound PRIVATE previews. No upload."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

from scripts.kesher_daily_pipeline import source_metadata, clean_article_html
from scripts.kesher_owner_positivity_preview import (
    sha_file, sha_bytes, make_image, encode_scene, join_scenes,
    merge_wavs, review_frames, verify_video, MODEL_SHA, G2P_SHA,
)

ROOT = Path(__file__).resolve().parents[1]
SLUG = "gratitude-relationship-genuine-thank-you"
SOURCE_SHA = "d4921756c12061359fca7cefea175387b534735d1af841a59e46a392edcc8c5f"
ARTICLE_BODY_SHA = "da21f981a32e6aacff2efc054cb5846a692371dc63a0a39c49776d9dae3598c0"
ARTICLE_DATE = "2026-11-11"
MEDIA_SOURCE = ROOT / "research/daily-2026-11-11-gratitude-media-plan.md"
IMAGES = (
    ("public/images/generated/blog/gratitude-relationship-genuine-thank-you-photo.png", "64580e5f0db8cf5a8924e32ee6b2672afeb8e5cfe36e15b4ca27f20a1d4cce7f"),
    ("public/images/blog/gratitude-relationship-genuine-thank-you-chores.png", "05ff114adda43c7253f374159379d5222f1e4d10d2c1e1f173d8a7caae41b5af"),
    ("public/images/blog/gratitude-relationship-genuine-thank-you-family.png", "647fa57bcf8bcb046e9da440b22baa3d243faa213331d6f8d9cbe5864c49212e"),
    ("public/images/blog/gratitude-relationship-genuine-thank-you-dinnertime.png", "79a1f5859da6ef0e563a55cdda8fa2dad2201599f8d70f0ec17192ecf2135d6a"),
    ("public/images/blog/gratitude-relationship-genuine-thank-you-laundry.png", "1575564cffcbb9e66ccb33e5afa991f79a7efde54e9949586dc6e5a6033e393c"),
)
VISUAL_LICENSE = "https://helpx.adobe.com/firefly/web/get-started/learn-the-basics/adobe-firefly-faq.html"
KINDS = ("overview", "short")
NARRATION = {
    "overview": (
        "לפעמים אנחנו אומרים תודה מתוך הרגל, אבל בני הזוג שלנו עדיין מרגישים שלא רואים אותם. למשל, הוא מכין ארוחת ערב אחרי יום עמוס, והיא נזכרת לומר תודה רק כששואלים אותה. מה חסר במילה הקטנה הזאת?",
        "החוקרת שרה אלגו ועמיתותיה עקבו אחרי רגעים של הכרת תודה אצל זוגות החיים יחד. הכרת תודה במפגשים יומיומיים נקשרה ליותר קרבה ושביעות רצון ביום שלאחר מכן. חשוב לדייק: זה קשר מחקרי, לא הבטחה שמילה אחת תפתור משבר.",
        "מחקר נוסף, של אמיי גורדון ועמיתיה, מצא שאנשים שהרגישו מוערכים נטו להעריך יותר את בני זוגם. ההערכה נקשרה לתגובה טובה יותר לצרכים ולמחויבות לקשר. לא מדובר בהוכחה שכל מחמאה מצילה נישואין.",
        "אז במקום להגיד רק תודה על הכול, נסו לזהות מעשה ממשי. ראיתי שהכנת ארוחת ערב למרות שהיה לך יום קשה. זה אפשר לי לנוח קצת, ואני מעריכה את זה. אמרנו מה ראינו, מה היה המאמץ ומה זה נתן לנו.",
        "אבל הוקרה אינה תחליף לחלוקת אחריות הוגנת בבית. ותודה שמרגישה מוגזמת או מזויפת עלולה אפילו להרחיק. היום בחרו מעשה קטן ואמיתי אחד, אמרו עליו תודה בלי לצפות לתמורה. למאמר המלא ולמקורות, הקישור בתיאור הסרטון באתר קשר.",
    ),
    "short": (
        "אומרים תודה לבן הזוג, אבל הוא עדיין מרגיש שלא רואים אותו? לא תמיד עוד תודה היא הפתרון.",
        "מחקרים מצאו קשר בין הכרת תודה יומיומית בזוגיות לבין תחושת קרבה ומחויבות, אבל הם לא מבטיחים פתרון קסם.",
        "נסו לומר: ראיתי שהכנת ארוחת ערב למרות שהיה לך יום קשה. זה ממש הקל עליי. תודה.",
        "כלומר, אומרים מה ראינו, איזה מאמץ זיהינו ואיך זה עזר. בלי דקלום ובלי לדרוש תודה בחזרה.",
        "והכי חשוב: אל תשתמשו בתודה במקום חלוקה הוגנת של העבודה בבית. למאמר ולמחקרים, הקישור בתיאור.",
    ),
}

def source_check():
    posts = json.loads((ROOT / "src/data/postsRecent.json").read_text(encoding="utf-8"))
    rows = [r for r in posts if r.get("slug") == SLUG and r.get("id") == SLUG]
    if len(rows) != 1 or rows[0].get("date") != ARTICLE_DATE:
        raise ValueError("DAILY_SOURCE_NOT_UNIQUE_OR_DATE_MISMATCH")
    row = rows[0]
    source = source_metadata(row)
    if source["content_sha256"] != SOURCE_SHA or sha_bytes(clean_article_html(row["content"]).encode()) != ARTICLE_BODY_SHA:
        raise ValueError("DAILY_SOURCE_HASH_MISMATCH")
    if not MEDIA_SOURCE.is_file() or not MEDIA_SOURCE.read_text(encoding="utf-8").startswith("# KESHER — 2026-11-11"):
        raise ValueError("MISSING_USER_APPROVED_DAILY_MEDIA_PLAN")
    for path, sha in IMAGES:
        p = ROOT / path
        if not p.is_file() or p.is_symlink() or sha_file(p) != sha:
            raise ValueError("LICENSED_PHOTO_MISSING_OR_ALTERED: " + path)
    from PIL import Image
    for path, _ in IMAGES:
        with Image.open(ROOT / path) as im:
            im.verify()
    if any(len(segments) != 5 for segments in NARRATION.values()):
        raise ValueError("EXACT_SCENE_PLAN")
    if "לא הבטחה" not in " ".join(NARRATION["overview"]) and "לא הבטחה" not in " ".join(NARRATION["short"]):
        # Narration must retain explicit scientific limitation (equivalent phrasing above).
        if "לא מדובר בהוכחה" not in " ".join(NARRATION["overview"]):
            raise ValueError("SCIENTIFIC_CAVEAT_MISSING")
    return source

def preview(output: Path):
    source_check()
    if output.exists():
        raise ValueError("PREVIEW_ALREADY_EXISTS_NO_DUPLICATE")
    output.mkdir(parents=True)
    sys.path.insert(0, str(ROOT / "scripts"))
    import kesher_owner_vantage_short as voice
    all_scenes = [(kind + "-" + str(i), text) for kind in KINDS for i, text in enumerate(NARRATION[kind])]
    voice.SCENES = all_scenes
    voices, durations, info = voice.speak(output)
    if len(voices) != 10 or info["model_revision"] != MODEL_SHA or info["g2p_revision"] != G2P_SHA:
        raise ValueError("VOICE_MODEL_CHANGED")
    if (info["weights_license"], info["reference_license"], info["g2p_license"]) != ("MIT", "CC BY 4.0", "Apache-2.0"):
        raise ValueError("VOICE_COMMERCIAL_RIGHTS_UNVERIFIED")
    for index,kind in enumerate(KINDS):
        loc = output / kind
        loc.mkdir()
        voicepaths = voices[index*5:(index+1)*5]
        seconds = durations[index*5:(index+1)*5]
        clips = []
        for i, original_index in enumerate((0,3,4,2,1) if kind=="overview" else (4,0,3,1,2)):
            canvas=loc / ("frame-%02d.jpg"%(i+1))
            make_image(ROOT / IMAGES[original_index][0], canvas, kind)
            clip=loc / ("scene-%02d.mp4"%(i+1))
            encode_scene(canvas, voicepaths[i], clip, kind, seconds[i]+0.06, i%2==1)
            clips.append(clip)
        video=output/(kind+".mp4")
        join_scenes(clips, video)
        audio=output/(kind+"-review-voice.wav")
        merge_wavs(voicepaths, audio)
        media=verify_video(video, kind)
        frames,contact=review_frames(video, output,kind)
        manifest={
            "source_slug":SLUG,"content_sha256":SOURCE_SHA,
            "source_date":ARTICLE_DATE,"track":"automatic_daily",
            "media_item_id":"owner-daily-"+kind+"-20261111-"+SOURCE_SHA[:12],
            "kind":kind,
            "source_file":"src/data/postsRecent.json",
            "source_body_sha256":ARTICLE_BODY_SHA,
            "research_file":"research/daily-2026-11-11-gratitude-media-plan.md",
            "research_file_sha256":sha_file(MEDIA_SOURCE),
            "script_segments":NARRATION[kind],
            "script_sha256":sha_bytes("\n".join(NARRATION[kind]).encode()),
            "visual_assets":[{"path":p,"sha256":sha,"provider":"Adobe Firefly","commercial_use_permitted":True,"license_url":VISUAL_LICENSE} for p,sha in IMAGES],
            "voice_provenance":info,
            "video_sha256":sha_file(video),
            "audio_sha256":sha_file(audio),
            "contact_sha256":sha_file(contact),
            "frame_sha256":[sha_file(p) for p in frames],
            "media":media,
            "quality":"QA_PENDING_INDEPENDENT_AUDIO_VISUAL_SEMANTIC_REVIEW",
            "rights":"PROVENANCE_ONLY_INDEPENDENT_RELEASE_REVIEW_REQUIRED",
            "delivery":"NOT_STARTED_PRIVATE_BINARY","uploaded":False,"public":False
        }
        (output/(kind+"-manifest.json")).write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("OWNER_DAILY_PREVIEW_READY",kind,manifest["video_sha256"],media,flush=True)
    print("PRIVATE_OWNED_MEDIA_READY_NO_UPLOAD",flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("action", choices=["preflight","preview"])
    p.add_argument("--source-sha",required=True)
    p.add_argument("--output",type=Path,default=Path("owner-daily-gratitude-output"))
    args=p.parse_args()
    if args.source_sha != SOURCE_SHA:
        raise SystemExit("EXACT_DAILY_SOURCE_HASH_REQUIRED")
    if args.action == "preflight":
        print("DAILY_ARTICLE_SOURCE_PREFLIGHT_OK",source_check()["content_sha256"])
    else:
        preview(args.output)
