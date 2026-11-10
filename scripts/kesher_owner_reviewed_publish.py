"""Publish only exact already reviewed OWNER media; no generation or fallback."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

from scripts import kesher_owner_asynchrony_preview as gifted
from scripts import kesher_owner_positivity_preview as positivity
from scripts.kesher_owner_vantage_short import youtube_client
from scripts.kesher_daily_pipeline import clean_article_html, source_metadata
from scripts.kesher_runtime.bridge_admission import main as bridge_admission
from scripts.kesher_runtime.media_worker import require_owner_media_quality

ROOT = Path(__file__).resolve().parents[1]
CHANNEL = "UCx5fEFvdVf28HLAR2dFW64Q"
KINDS = ("overview", "short")
CONFIG = {
    gifted.SLUG: {
        "module": gifted, "date": "20261109", "artifact": 13710593150,
        "canonical_sha": "c4bc90e101bd495f5f91d17793f59e216eb544ee828f4632b8fe5d7fedb259f3",
        "run": 42699460010,
        "zip_sha": "6704e43b29bfd9a7c08386964b1f8d83a35e9be839e7cb582527f7b1a9f3cfb8",
        "titles": {
            "overview": "ילד מחונן שמרגיש לבד? להבין התפתחות א־סינכרונית",
            "short": "ילד מחונן, רגשות של ילד: מה הורים יכולים לעשות? #Shorts",
        },
        "intro": "מה קורה כשהחשיבה מתקדמת מהר יותר מהוויסות הרגשי? איך מזהים את הפער ומגיבים בלי לצפות מילד להתנהג כמבוגר?",
        "tags": ["ילדים מחוננים", "התפתחות א סינכרונית", "הדרכת הורים", "שירה סהרוני"],
    },
    positivity.SLUG: {
        "module": positivity, "date": "20261110", "artifact": 13745350527,
        "canonical_sha": "65e7b616d7c77983a013d3b7b9c4e4f7fe6101b311c2c02fb17a6a8f49b31c3f",
        "run": 42778087294,
        "zip_sha": "c4401eb33f3a6937c78455ea30d76af162a1dd96af98368e4a4e5d494531da76",
        "titles": {
            "overview": "תהודה חיובית בזוגיות: איך רגעים קטנים מחזקים את החיבור?",
            "short": "שלושה רגעים קטנים של חיבור בזוגיות #Shorts",
        },
        "intro": "מהי תהודה חיובית בזוגיות? מחקר תצפיתי על רגעי חיבור ותרגיל קצר שאפשר לנסות בבית, בלי הבטחות מופרזות.",
        "tags": ["תהודה חיובית", "ייעוץ זוגי", "זוגיות", "שירה סהרוני"],
    },
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def source_config(slug, source_sha):
    cfg = CONFIG.get(slug)
    require(cfg is not None and cfg["canonical_sha"] == source_sha,
            "EXACT_APPROVED_SOURCE_REQUIRED")
    return cfg


def verify_source_binding(cfg, post=None):
    """Bind the immutable preview's body digest to the actual canonical source.

    The older preview hash covers only cleaned article content. The production
    source contract covers title, excerpt, that content, and canonical URL.
    Both must be recomputed from the same exact committed post; neither is an
    interchangeable alias or an exemption from the production identity gate.
    """
    module = cfg["module"]
    if post is None:
        posts = json.loads((ROOT / "src/data/postsRecent.json").read_text(encoding="utf-8"))
        selected = [x for x in posts if x.get("slug") == module.SLUG]
        require(len(selected) == 1, "ARTICLE_SOURCE_NOT_UNIQUE")
        post = selected[0]
    source = source_metadata(post)
    body_sha = hashlib.sha256(clean_article_html(str(post["content"])).encode("utf-8")).hexdigest()
    require(source["slug"] == module.SLUG
            and source["canonical_url"] == module.ARTICLE
            and source["content_sha256"] == cfg["canonical_sha"]
            and body_sha == module.SOURCE_SHA, "CANONICAL_SOURCE_BINDING_MISMATCH")
    return post


def item_id(cfg, kind):
    return f"owner-{kind}-{cfg['date']}-{cfg['module'].SOURCE_SHA[:12]}"


def archive_files(archive, dest, cfg):
    """Accept only the exact immutable GitHub artifact and safe expected files."""
    require(sha(archive) == cfg["zip_sha"], "ARTIFACT_DIGEST_MISMATCH")
    expected = set()
    for kind in KINDS:
        expected.update((f"{kind}.mp4", f"{kind}-manifest.json",
                         f"{kind}-review-voice.wav", f"{kind}-visual-contact-sheet.jpg"))
        expected.update(f"{kind}-frame-{i:02d}.jpg" for i in range(1, 9))
        if cfg["module"] is positivity:
            expected.add(f"{kind}-asr.txt")
    if cfg["module"] is positivity:
        expected.add("asr-review.json")
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        require(len(names) == len(set(names)) and set(names) == expected,
                "ARTIFACT_FILE_SET_MISMATCH")
        require(sum(x.file_size for x in z.infolist()) < 100_000_000,
                "ARTIFACT_TOO_LARGE")
        for name in sorted(expected):
            require(Path(name).name == name, "UNSAFE_ARTIFACT_PATH")
            (dest / name).write_bytes(z.read(name))


def validate_bundle(cfg, directory, kind):
    module = cfg["module"]
    slug, artifact_body_sha = module.SLUG, module.SOURCE_SHA
    source_sha = cfg["canonical_sha"]
    verify_source_binding(cfg)
    root = ROOT / "research/owner-media-quality"
    approval = json.loads((root / f"{slug}--{kind}.json").read_text(encoding="utf-8"))
    manifest_path = directory / f"{kind}-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence = approval["evidence"]
    require(evidence.get("github_artifact_id") == cfg["artifact"]
            and evidence.get("github_run") == cfg["run"], "ARTIFACT_APPROVAL_MISMATCH")
    binding = evidence.get("source_binding") or {}
    require(binding.get("artifact_body_sha256") == artifact_body_sha
            and binding.get("canonical_content_sha256") == source_sha
            and binding.get("method") == "recomputed_same_committed_post_body_and_canonical_source"
            and bool(binding.get("verified_at")), "CANONICAL_APPROVAL_BINDING_MISMATCH")
    require(manifest.get("source_slug") == slug
            and manifest.get("content_sha256") == artifact_body_sha
            and manifest.get("kind") == kind
            and manifest.get("media_item_id") == item_id(cfg, kind)
            and manifest.get("uploaded") is False and manifest.get("public") is False,
            "MANIFEST_IDENTITY_MISMATCH")
    require(manifest.get("source_file") == str(module.RESEARCH.relative_to(ROOT)),
            "SOURCE_FILE_MISMATCH")
    video = directory / f"{kind}.mp4"
    wav = directory / f"{kind}-review-voice.wav"
    contact = directory / f"{kind}-visual-contact-sheet.jpg"
    frames = {f"{kind}-frame-{i:02d}.jpg": sha(directory / f"{kind}-frame-{i:02d}.jpg")
              for i in range(1, 9)}
    transcript = (directory / f"{kind}-asr.txt" if module is positivity else
                  root / "evidence" / f"{slug}--{kind}-descript-transcript.txt")
    require(sha(video) == manifest["video_sha256"]
            and sha(wav) == manifest["audio_sha256"] == evidence["audio_sha256"]
            and sha(contact) == manifest["contact_sha256"]
            and list(frames.values()) == manifest["frame_sha256"]
            and sha(module.RESEARCH) == manifest["source_file_sha256"],
            "IMMUTABLE_MEDIA_EVIDENCE_MISMATCH")
    voice = manifest["voice_provenance"]
    require(manifest["voice_model"] == "BlueTTS2.5-onnx:libri_female_6147"
            and voice["model_revision"] == module.MODEL_SHA
            and voice["g2p_revision"] == module.G2P_SHA
            and voice["weights_license"] == "MIT"
            and voice["reference_license"] == "CC BY 4.0"
            and voice["g2p_license"] == "Apache-2.0"
            and voice["voice_preset"] == "libri_female_6147"
            and voice["reference_license_url"] == "https://www.openslr.org/141/",
            "VOICE_LICENSE_PROVENANCE_MISMATCH")
    scripts, provenance = module.source_check(public=False)
    require(manifest["script_segments"] == scripts[kind]
            and manifest["visual_sources"] == provenance["images"],
            "REVIEWED_SOURCE_OR_VISUALS_CHANGED")
    module.verify_video(video, kind)
    item = {
        "technical_verified": True, "source": {"slug": slug, "content_sha256": source_sha},
        "type": "video_overview" if kind == "overview" else "article_short",
        "id": item_id(cfg, kind), "final_sha256": sha(video),
        "manifest_sha256": sha(manifest_path), "transcript_sha256": sha(transcript),
        "visual_review_sha256": sha(contact), "source_file_sha256": sha(module.RESEARCH),
        "frame_sha256": frames,
    }
    require_owner_media_quality(item, kind, approval_root=root)
    return video


def metadata(cfg, kind, overview_id=None):
    module = cfg["module"]
    description = (
        cfg["intro"] + "\n\nלמאמר המלא והמקורות: " + module.ARTICLE
        + "\n\nקראו עוד באתר KESHER — שירה סהרוני."
        + "\nKESHER_OWNER_MEDIA_ITEM=" + item_id(cfg, kind)
        + "\nsource_slug=" + module.SLUG + "\ncontent_sha256=" + cfg["canonical_sha"]
        + "\nקריינות סינתטית: BlueTTS 2.5 (MIT), RenikudPlus (Apache 2.0), "
          "LibriTTS-R / Google LLC, דוברת 6147 (CC BY 4.0)."
        + "\nhttps://huggingface.co/notmax123/BlueTTS2.5-onnx"
        + "\nhttps://huggingface.co/notmax123/RenikudPlus"
        + "\nhttps://www.openslr.org/141/"
        + "\nhttps://creativecommons.org/licenses/by/4.0/"
        + ("\nתמונות מקוריות שנוצרו עבור KESHER באמצעות Adobe Firefly."
           if module is positivity else "\nתמונות מקוריות שנוצרו עבור KESHER באמצעות OpenAI.")
    )
    if kind == "short":
        require(isinstance(overview_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", overview_id),
                "PUBLIC_OVERVIEW_REQUIRED_FIRST")
        description += ("\nלסרטון המלא בערוץ: https://www.youtube.com/watch?v=" + overview_id
                        + "\nאפשר לפתוח את הסרטון המלא בעמוד הערוץ אם הקישור אינו לחיץ ב-Shorts.")
    return {"title": cfg["titles"][kind], "description": description,
            "categoryId": "22", "tags": cfg["tags"],
            "defaultLanguage": "he", "defaultAudioLanguage": "he"}


def classify(cfg, records):
    """Fail closed on duplicate or ambiguous article identity, including older metadata."""
    module = cfg["module"]
    matches = {}
    for row in records:
        snip = row.get("snippet") or {}
        require(snip.get("channelId") == CHANNEL, "UNEXPECTED_CHANNEL")
        desc = str(snip.get("description") or "")
        title = str(snip.get("title") or "")
        relevant = (module.SLUG in desc or module.SOURCE_SHA in desc or cfg["canonical_sha"] in desc
                    or title in cfg["titles"].values())
        if not relevant:
            continue
        exact = [k for k in KINDS if "KESHER_OWNER_MEDIA_ITEM=" + item_id(cfg, k) in desc]
        require(len(exact) == 1 and "source_slug=" + module.SLUG in desc
                and "content_sha256=" + cfg["canonical_sha"] in desc,
                "AMBIGUOUS_EXISTING_SOURCE_VIDEO")
        kind = exact[0]
        require(kind not in matches, "DUPLICATE_SOURCE_VIDEO_IDENTITY")
        matches[kind] = row
    return matches


def scan(yt, cfg):
    rows = yt.channels().list(part="id,contentDetails", mine=True).execute().get("items", [])
    require(len(rows) == 1 and rows[0]["id"] == CHANNEL, "WRONG_YOUTUBE_CHANNEL")
    playlist = rows[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, seen_tokens, token = [], set(), None
    while True:
        page = yt.playlistItems().list(part="contentDetails", playlistId=playlist,
                                       maxResults=50, pageToken=token).execute()
        ids.extend(x["contentDetails"]["videoId"] for x in page.get("items", []))
        token = page.get("nextPageToken")
        if not token:
            break
        require(token not in seen_tokens and len(seen_tokens) < 200, "INCOMPLETE_DEDUP_SCAN")
        seen_tokens.add(token)
    require(len(ids) == len(set(ids)), "DUPLICATE_UPLOAD_PLAYLIST_ID")
    records = []
    for i in range(0, len(ids), 50):
        records.extend(yt.videos().list(part="snippet,status,processingDetails",
                       id=",".join(ids[i:i+50])).execute().get("items", []))
    require({x["id"] for x in records} == set(ids), "INCOMPLETE_VIDEO_DEDUP_SCAN")
    return classify(cfg, records)


def verify_public(yt, cfg, kind, vid, expected):
    import requests
    require(re.fullmatch(r"[A-Za-z0-9_-]{11}", vid), "INVALID_VIDEO_ID")
    for _ in range(24):
        rows = yt.videos().list(part="snippet,status,processingDetails,player",
                                id=vid).execute().get("items", [])
        if rows:
            row = rows[0]
            snip, status = row["snippet"], row["status"]
            proc = (row.get("processingDetails") or {}).get("processingStatus")
            require(snip["channelId"] == CHANNEL, "WRONG_VIDEO_CHANNEL")
            require(snip.get("title") == expected["title"]
                    and snip.get("description") == expected["description"],
                    "PUBLIC_VIDEO_METADATA_MISMATCH")
            require(proc not in {"failed", "terminated"}, "YOUTUBE_PROCESSING_FAILED")
            if (status.get("privacyStatus") == "public" and proc == "succeeded"
                    and status.get("embeddable") is True
                    and vid in (row.get("player") or {}).get("embedHtml", "")):
                response = requests.get("https://www.youtube.com/oembed",
                    params={"url": "https://www.youtube.com/watch?v=" + vid, "format": "json"},
                    timeout=20)
                if response.status_code == 200 and vid in response.json().get("html", ""):
                    url = "https://www.youtube.com/" + ("shorts/" if kind == "short" else "watch?v=") + vid
                    print("OWNER_PUBLIC_VERIFIED " + json.dumps({
                        "kind": kind, "url": url, "id": vid, "source_slug": cfg["module"].SLUG,
                        "content_sha256": cfg["canonical_sha"], "privacy": "public",
                        "processing": "succeeded", "channel": CHANNEL, "player": "verified",
                        "article": cfg["module"].ARTICLE,
                    }, ensure_ascii=False), flush=True)
                    return vid
        time.sleep(10)
    raise RuntimeError("PUBLIC_PROCESSING_OR_PLAYER_PENDING_DO_NOT_REUPLOAD")


def verify_live_article(cfg):
    """Require production manifest, exact source marker and actual live hero bytes."""
    import requests
    module = cfg["module"]
    post = verify_source_binding(cfg)
    module.source_check(public=True)
    site = "https://kesher.saharoni.com"
    manifest_response = requests.get(site + "/.well-known/kesher-publication.json", timeout=30)
    require(manifest_response.status_code == 200, "LIVE_PUBLICATION_MANIFEST_UNAVAILABLE")
    manifest = manifest_response.json()
    row = manifest.get("articles", {}).get(module.SLUG) or {}
    identity = row.get("identity") or {}
    require(identity.get("slug") == module.SLUG
            and identity.get("content_sha256") == cfg["canonical_sha"]
            and row.get("canonical_url") == module.ARTICLE,
            "LIVE_ARTICLE_SOURCE_IDENTITY_MISMATCH")
    require(row.get("title") == post["title"], "LIVE_ARTICLE_TITLE_MISMATCH")
    hero = row.get("hero") or {}
    require(hero.get("path") == post["image"]
            and hero["path"].startswith("/images/generated/blog/"),
            "LIVE_ARTICLE_HERO_IDENTITY_MISMATCH")
    page = requests.get(module.ARTICLE, timeout=30)
    require(page.status_code == 200
            and f'<meta name="kesher:content-sha256" content="{cfg["canonical_sha"]}">' in page.text
            and hashlib.sha256(page.content).hexdigest() == row.get("html_sha256")
            and f'rel="canonical" href="{module.ARTICLE}"' in page.text,
            "LIVE_ARTICLE_CONTENT_MARKER_MISMATCH")
    image = requests.get(site + hero["path"], timeout=30)
    require(image.status_code == 200 and image.headers.get("Content-Type", "").startswith("image/")
            and hashlib.sha256(image.content).hexdigest() == hero.get("sha256")
            and sha(ROOT / "public" / hero["path"].lstrip("/")) == hero.get("sha256"),
            "LIVE_ARTICLE_HERO_BYTES_MISMATCH")
    print("OWNER_ARTICLE_LIVE_VERIFIED " + module.ARTICLE + " " + cfg["canonical_sha"], flush=True)


def publish(cfg, directory):
    from googleapiclient.http import MediaFileUpload
    # All assets and article must pass before the first public mutation.
    verify_live_article(cfg)
    paths = {kind: validate_bundle(cfg, directory, kind) for kind in KINDS}
    yt = youtube_client()
    overview_id = None
    for kind in KINDS:
        expected = metadata(cfg, kind, overview_id)
        matches = scan(yt, cfg)
        if kind in matches:
            vid = matches[kind]["id"]
            print("OWNER_EXISTING_EXACT_VIDEO " + kind + " " + vid, flush=True)
        else:
            # Re-read the existing admission fence immediately before each insert.
            require(bridge_admission([]) == 0, "BRIDGE_ADMISSION_DENIED")
            print("OWNER_UPLOAD_STARTED " + item_id(cfg, kind), flush=True)
            upload = yt.videos().insert(part="snippet,status",
                body={"snippet": expected, "status": {
                    "privacyStatus": "public", "selfDeclaredMadeForKids": False,
                    "embeddable": True,
                }},
                media_body=MediaFileUpload(str(paths[kind]), mimetype="video/mp4", resumable=True))
            result = None
            while result is None:
                _, result = upload.next_chunk(num_retries=0)
            vid = result["id"]
            print("OWNER_UPLOAD_ID " + kind + " " + vid, flush=True)
        verified = verify_public(yt, cfg, kind, vid, expected)
        if kind == "overview":
            overview_id = verified
    final = scan(yt, cfg)
    require(set(final) == set(KINDS), "FINAL_DEDUP_VERIFICATION_FAILED")
    print("OWNER_TWO_PUBLIC_ASSETS_VERIFIED", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    cfg = source_config(args.slug, args.source_sha)
    require(bridge_admission([]) == 0, "BRIDGE_ADMISSION_DENIED")
    with tempfile.TemporaryDirectory(prefix="kesher-owner-reviewed-") as temp:
        dest = Path(temp)
        archive = dest / "artifact.zip"
        with archive.open("wb") as f:
            subprocess.run(["gh", "api", f"repos/yanivsa/kesher-website/actions/artifacts/{cfg['artifact']}/zip"],
                           stdout=f, check=True, timeout=120)
        archive_files(archive, dest, cfg)
        publish(cfg, dest)


if __name__ == "__main__":
    main()
