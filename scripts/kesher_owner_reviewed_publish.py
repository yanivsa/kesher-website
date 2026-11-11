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
from scripts import kesher_owner_productive_failure_preview as productive
from scripts import kesher_owner_7500_preview as code7500
from scripts import kesher_owner_kindergarten_play_preview as kindergarten
from scripts import kesher_owner_kindergarten_audio_repair as kindergarten_repair
from scripts import kesher_owner_midyear_kindergarten_preview as midyear
from scripts import kesher_owner_midyear_kindergarten_repair as midyear_repair
from scripts import kesher_owner_midyear_kindergarten_cta_repair as midyear_cta
from scripts import kesher_owner_separate_room_preview as separate_room
from scripts import kesher_owner_separate_room_pronunciation_repair as separate_room_repair
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
    productive.SLUG: {
        "module": productive, "date": "20261110", "artifact": 13757967291,
        "canonical_sha": "3c591714830cf7787c453be6b11eab3d7eb8e743eed97da69d449acc9a80b5bf",
        "run": 42805342726,
        "zip_sha": "08962f9d423d0310ebb92c5c8e0dba29a9cd9e753563068917232c90c13b5529",
        "titles": {
            "overview": "כישלון פורה: למה לא לפתור לילד כל קושי בשיעורי הבית?",
            "short": "הילד נתקע בשיעורי הבית? נסו לשאול את זה #Shorts",
        },
        "intro": "מהו כישלון פורה, מתי כדאי לתת לילד לנסות לפני שמסבירים, ומתי דווקא לעזור מיד? דוגמה מעשית וממצאים ממחקרי למידה, בלי להבטיח פתרון שמתאים לכל ילד.",
        "tags": ["כישלון פורה", "שיעורי בית", "למידה", "הדרכת הורים", "שירה סהרוני"],
    },
    code7500.SLUG: {
        "module": code7500, "date": "20261110", "artifact": 13764754562,
        "canonical_sha": code7500.CANONICAL_SHA, "run": 42819300794,
        "zip_sha": "9b5e785d8da39501501a809f68c20634441fe0163d795d773f62e2bb3739ebd4",
        "titles": {
            "overview": "איך יודעים שהזוגיות במשבר? 5 סימנים שלא כדאי להתעלם מהם",
            "short": "זלזול בזוגיות: הסימן שהריב כבר לא רק על הנושא",
        },
        "intro": "חמישה סימנים למשבר בזוגיות, מה אפשר לשנות ומתי חשוב לפנות לעזרה. קוד 7500 הוא מטאפורה בלבד; אין כאן אבחנה או תחזית לגירושין.",
        "intro_by_kind": {"short": "כשוויכוח עובר מהבעיה אל האישיות, הקשר משלם את המחיר. דוגמה לתלונה ממוקדת במקום זלזול, וחשיבות הבטיחות כשיש פחד או אלימות."},
        "tags": ["איך יודעים שהזוגיות במשבר", "סימנים למשבר בזוגיות", "תקשורת זוגית", "ריבים בזוגיות"],
        "tags_by_kind": {"short": ["זלזול בזוגיות", "בוז בזוגיות", "ריבים בזוגיות", "תקשורת בזמן ריב"]},
    },
    kindergarten.SLUG: {
        "module": kindergarten, "date": "20261110", "artifact": 13788929727,
        "canonical_sha": kindergarten.CANONICAL_SHA, "body_sha": kindergarten.BODY_SHA,
        "artifact_identity_sha": kindergarten.SOURCE_SHA, "run": 42872924288,
        "zip_sha": "f5aaec2aa660d75dfe8d89bd82c0c0b6e944269ca1f3617969384dae3e3cc5a5",
        "titles": {
            "overview": "ילד לא משחק בגן? מתי לתת לו זמן ומתי לעזור?",
            "short": "הילד יושב בצד בגן? לא תמיד צריך להתערב #Shorts",
        },
        "intro": "ילד יושב בצד בגן: איך מבדילים בין משחק עצמאי רגוע לבין ילד שרוצה להצטרף אבל חושש? שאלות לגננת, צעד קטן בלי לחץ ומתי לפנות לרופא הילדים.",
        "tags": ["ילד לא משחק בגן", "ילד יושב בצד בגן", "ביישנות ילדים", "הדרכת הורים", "שירה סהרוני"],
    },
    midyear.SLUG: {
        "module": midyear, "date": "20261110", "artifact": 13797277927,
        "canonical_sha": midyear.CANONICAL_SHA, "body_sha": midyear.BODY_SHA,
        "artifact_identity_sha": midyear.SOURCE_SHA, "run": 42889104063,
        "zip_sha": "89d38d449772bc1a5b4983b27677e26c5716a5c7de3214d4c8b385dea789fb06",
        "source_catalog": "posts.json",
        "titles": {
            "overview": "מעבר גן באמצע שנה: איך לעזור לילד להרגיש בטוח בגן החדש?",
            "short": "הילד עובר גן באמצע שנה? 3 צעדים שיעזרו #Shorts",
        },
        "intro": "מעבר גן באמצע שנה: איך להכין את הילד, להיפרד מהגן הישן, לתאם פרידה עם הגננת ולבדוק מה קורה אחרי שיוצאים. אין זמן הסתגלות אחד שמתאים לכולם.",
        "tags": ["מעבר גן באמצע שנה", "הסתגלות לגן חדש", "הדרכת הורים", "שירה סהרוני"],
    },
    separate_room.SLUG: {
        "module": separate_room, "date": "20261111", "artifact": 13817130469,
        "canonical_sha": separate_room.SOURCE_SHA, "body_sha": separate_room.BODY_SHA,
        "artifact_identity_sha": separate_room.SOURCE_SHA, "run": 42931461922,
        "research_path": separate_room.PLAN,
        "zip_sha": "7a1150726561503cb924dae8a96ed2c53c13dd293efbf3dbab95b52664c1d2b8",
        "titles": {
            "overview": "מעבר לחדר נפרד: איך לעזור לילד לישון בחדר שלו בלי מאבק?",
            "short": "מעבר לחדר נפרד: קודם בודקים את גיל הילד #Shorts",
        },
        "intro": "מתי מתאים מעבר לחדר נפרד? ההבדל בין שינה בטוחה לתינוקות לבין הסתגלות הדרגתית של פעוטות, טקס ערב קבוע וליווי רגוע בלי להתעלם ממצוקה.",
        "tags": ["מעבר לחדר נפרד", "שינה בטוחה לתינוקות", "שינת פעוטות", "הדרכת הורים", "שירה סהרוני"],
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


def body_identity(cfg):
    return cfg.get("body_sha", cfg["module"].SOURCE_SHA)


def artifact_identity(cfg):
    return cfg.get("artifact_identity_sha", cfg["module"].SOURCE_SHA)


def verify_source_binding(cfg, post=None):
    """Bind the immutable preview's body digest to the actual canonical source.

    The older preview hash covers only cleaned article content. The production
    source contract covers title, excerpt, that content, and canonical URL.
    Both must be recomputed from the same exact committed post; neither is an
    interchangeable alias or an exemption from the production identity gate.
    """
    module = cfg["module"]
    if post is None:
        catalog = cfg.get("source_catalog", "postsRecent.json")
        require(catalog in {"postsRecent.json", "posts.json"}, "UNAPPROVED_SOURCE_CATALOG")
        posts = json.loads((ROOT / "src/data" / catalog).read_text(encoding="utf-8"))
        selected = [x for x in posts if x.get("slug") == module.SLUG]
        require(len(selected) == 1, "ARTICLE_SOURCE_NOT_UNIQUE")
        post = selected[0]
    source = source_metadata(post)
    body_sha = hashlib.sha256(clean_article_html(str(post["content"])).encode("utf-8")).hexdigest()
    require(source["slug"] == module.SLUG
            and source["canonical_url"] == module.ARTICLE
            and source["content_sha256"] == cfg["canonical_sha"]
            and body_sha == body_identity(cfg), "CANONICAL_SOURCE_BINDING_MISMATCH")
    return post


def item_id(cfg, kind):
    return f"owner-{kind}-{cfg['date']}-{artifact_identity(cfg)[:12]}"


def archive_files(archive, dest, cfg):
    """Accept only the exact immutable GitHub artifact and safe expected files."""
    require(sha(archive) == cfg["zip_sha"], "ARTIFACT_DIGEST_MISMATCH")
    expected = set()
    for kind in KINDS:
        expected.update((f"{kind}.mp4", f"{kind}-manifest.json",
                         f"{kind}-review-voice.wav", f"{kind}-visual-contact-sheet.jpg"))
        expected.update(f"{kind}-frame-{i:02d}.jpg" for i in range(1, 9))
        if cfg["module"] in (positivity, productive, code7500, kindergarten, midyear, separate_room):
            expected.add(f"{kind}-asr.txt")
    if cfg["module"] in (positivity, productive, code7500, kindergarten, midyear, separate_room):
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


def validate_productive_repair(manifest, video, kind):
    require(manifest.get("canonical_content_sha256") == productive.CANONICAL_SHA,
            "PRODUCTIVE_CANONICAL_MANIFEST_MISMATCH")
    if kind == "short":
        repair = manifest.get("visual_repair") or {}
        require(repair.get("input_artifact_id") == 13757158570
                and repair.get("input_archive_sha256") == productive.REPAIR_ARCHIVE_SHA
                and repair.get("original_video_sha256") == productive.REPAIR_SHORT_SHA
                and repair.get("audio_packets_preserved") is True
                and repair.get("scene_frame_boundaries") == [0,128,267,331,407,506,701,760]
                and repair.get("composition") == "full_frame_9_16_editorial_focus_crops_no_blurred_padding"
                and repair.get("audio_packet_sha256") == "92cba18305a9c229891f682279472716c489fc56228bbbcdafaeba9923466d9b",
                "PRODUCTIVE_SHORT_NATIVE_REPAIR_EVIDENCE_MISMATCH")
        require(productive._audio_packets(video) == repair["audio_packet_sha256"],
                "PRODUCTIVE_SHORT_AUDIO_PACKET_MISMATCH")
    else:
        require(sha(video) == productive.REPAIR_OVERVIEW_SHA,
                "PRODUCTIVE_OVERVIEW_REUSE_MISMATCH")


def validate_7500_repair(manifest, video, kind):
    require(manifest.get("canonical_content_sha256") == code7500.CANONICAL_SHA,
            "7500_CANONICAL_MANIFEST_MISMATCH")
    repair = manifest.get("targeted_repair") or {}
    expected = {
        "input_artifact_id": code7500.REPAIR_ARTIFACT,
        "input_archive_sha256": code7500.REPAIR_ARCHIVE_SHA,
        "original_short_sha256": code7500.REPAIR_SHORT_SHA,
        "overview_video_sha256": code7500.REPAIR_OVERVIEW_SHA,
        "changed_scene_index": 3, "prefix_frames": code7500.PREFIX_FRAMES,
        "prefix_frame_hashes_sha256": "ff197c2b69ba719ff0ea31df1d475ff8c9bacf054045156711cc703a7bf6b7a8",
        "prefix_aac_sha256": "1bc4f2e0ffb0499587ec017d47236d0185c3c1180d0c4b07a6fdff2a11846a9c",
        "prefix_aac_bytes": 512016, "prefix_pixels_and_aac_preserved": True,
    }
    require(repair == expected, "7500_TARGETED_REPAIR_EVIDENCE_MISMATCH")
    if kind == "overview":
        require(sha(video) == code7500.REPAIR_OVERVIEW_SHA, "7500_OVERVIEW_REUSE_MISMATCH")
    else:
        require(sha(video) == "83df806140023ca39f515dc83a1a9efc52b0c9caf0056ab437251795e2240066"
                and manifest.get("composition") == "native_full_frame_9_16_no_padding",
                "7500_SHORT_EXACT_NATIVE_MEDIA_MISMATCH")
        frames = code7500._frame_hashes(video)
        packets = code7500._aac_packets(video)
        require(len(frames) == 983
                and hashlib.sha256("\n".join(frames[:code7500.PREFIX_FRAMES]).encode()).hexdigest() == repair["prefix_frame_hashes_sha256"]
                and hashlib.sha256(packets[:repair["prefix_aac_bytes"]]).hexdigest() == repair["prefix_aac_sha256"],
                "7500_SHORT_REVIEWED_PREFIX_MISMATCH")


KINDERGARTEN_REPAIR_EVIDENCE = {
        "input_artifact_id": 13787755454,
        "input_archive_sha256": "bfd6fca1b962555d34ae02e652ec02775ccfd9e3d21d43c2b4ade2557c5b6ccb",
        "original_overview_sha256": "bfbd515e6d852935298b8cfdde5b037a5eb1abced9e21e36d9271937449c369e",
        "unchanged_short_sha256": "9e798a40b8a11bf07314662ebe7dc789c9c3f9c3de41a010924616d78f172a09",
        "overview_cut_samples": [
            3235176,
            3376958
        ],
        "short_cut_samples": [
            1163799,
            1290366
        ],
        "sample_rate": 44100,
        "video_packet_sha256": "e08b3589e1ea6a28744328f5a6e8482633ec05b1ebe92f33b8dd41b4230d30e8",
        "original_pcm_sha256": "296b5183350f75be78393c7da004fd4a8591a342b3396498a629fda68763a330",
        "edited_pcm_sha256": "3f7eccd93849dcb8d82e8d777f645f31810eb5de8bc87135dd939a5f6fdb3124",
        "outside_cut_pcm_sha256": "c9a1d2013a612856eca10777257e3a632fe125fa6cf5ad594b2bae0882d3a22d",
        "outside_cut_pcm_preserved_before_aac_encode": True,
        "video_packets_preserved": True,
        "original_short_preserved": True,
        "method": "reuse exact independently transcribed Short sentence at silent boundaries; no new TTS"
    }


def validate_kindergarten_repair(manifest, video, kind):
    require(manifest.get("canonical_content_sha256") == kindergarten.CANONICAL_SHA
            and manifest.get("article_body_sha256") == kindergarten.BODY_SHA,
            "KINDERGARTEN_CANONICAL_MANIFEST_MISMATCH")
    if kind == "overview":
        require(manifest.get("targeted_audio_repair") == KINDERGARTEN_REPAIR_EVIDENCE
                and sha(video) == "b4ab42789a64e302d8fc57759cc6a58efd9032b1626b9d8d017fa0b75ef23288",
                "KINDERGARTEN_TARGETED_AUDIO_REPAIR_MISMATCH")
        require(kindergarten_repair.sha(kindergarten_repair.video_packets(video))
                == KINDERGARTEN_REPAIR_EVIDENCE["video_packet_sha256"],
                "KINDERGARTEN_ORIGINAL_VIDEO_PACKETS_CHANGED")
    else:
        require(sha(video) == kindergarten_repair.SHORT_SHA
                and manifest.get("composition") == "native_full_frame_9_16_no_padding",
                "KINDERGARTEN_UNCHANGED_NATIVE_SHORT_MISMATCH")


MIDYEAR_CTA_EVIDENCE = {
    "input_artifact_id": 13796284317,
    "input_archive_sha256": "1bf0c28f2c9006416cfca78d92981a45025c210eb0662c9c173ab16ca77fe1c7",
    "original_overview_sha256": "e33c65f89e0864b02a927c9c7f0db152baaab2319171d43124db8f9a6ddbe607",
    "unchanged_short_sha256": "ca2c1f9f5ad64b8de93d5956dda543a1530cec988aef70185ee2ee230ae981e4",
    "overview_cut_samples": [
        3542112,
        3637368
    ],
    "short_cut_samples": [
        1096326,
        1186290
    ],
    "sample_rate": 44100,
    "video_packet_hashes_sha256": "13319b11e1d486cd4d917afc69ad7bc90ffeb76394282064bdaac71af794a0b5",
    "original_pcm_sha256": "223344f765740efc6d63547b65605b73deaa014616222864db3a93cca75c090e",
    "edited_pcm_sha256": "b4df89b08dca31ac430613eecdf1b377f65cd84b73ed19e825b38fba24972e1b",
    "outside_cut_pcm_sha256": "3ecb7fe261b82b4ed8d57a0c6e2ad12d8517692a3a9a43d8256e5b5a2cf83dc3",
    "outside_cut_pcm_preserved_before_aac_encode": True,
    "video_packets_preserved": True,
    "original_short_preserved": True,
    "method": "replace incomplete CTA with exact independently transcribed Short sentence at silent boundaries; no new TTS"
}


def validate_midyear_repair(manifest, video, kind):
    require(manifest.get("canonical_content_sha256") == midyear.CANONICAL_SHA
            and manifest.get("article_body_sha256") == midyear.BODY_SHA,
            "MIDYEAR_CANONICAL_MANIFEST_MISMATCH")
    if kind == "overview":
        require(manifest.get("targeted_cta_repair") == MIDYEAR_CTA_EVIDENCE
                and sha(video) == "e1234a8be83905aa7079c3c01f384c7aae1aba728d9f2ff3d8ce86e8446e0451",
                "MIDYEAR_CTA_REPAIR_MISMATCH")
        require(midyear_repair.sha("\n".join(midyear_repair.packet_hashes(video, "v:0")).encode())
                == MIDYEAR_CTA_EVIDENCE["video_packet_hashes_sha256"],
                "MIDYEAR_OVERVIEW_VIDEO_PACKETS_CHANGED")
    else:
        require(sha(video) == midyear_cta.SHORT_SHA
                and manifest.get("composition") == "native_full_frame_9_16_no_padding"
                and (manifest.get("targeted_duration_repair") or {}).get("original_video_and_audio_packets_preserved") is True,
                "MIDYEAR_SHORT_EXACT_NATIVE_MEDIA_MISMATCH")


SEPARATE_ROOM_FINAL_SHA = {
    "overview": "120e7bc1e022977835da0c26c330c7225953ed293705f2d114c40fadf18b8b67",
    "short": "9310212663d4305cf8c69169ca22f195daa82524baf6b88caff89bdbe517d18a",
}
SEPARATE_ROOM_PACKET_SHA = {
    "overview": "e9656cab127fe96cadd1fb98af4471193ee59a0918b11c116c8569df4b9f08f6",
    "short": "b6fc9b0c4b76ab0ef8a38fe1c82bf1de10e0f54ae9be5d3385238a7810f782d8",
}
SEPARATE_ROOM_ASR_SHA = "852b1fbd05416936c6190b6bf888b51083288ed2c9653c588bc9e04a93a56204"


def validate_separate_room_repair(manifest, video, kind):
    require(manifest.get("canonical_content_sha256") == separate_room.SOURCE_SHA
            and manifest.get("article_body_sha256") == separate_room.BODY_SHA,
            "SEPARATE_ROOM_CANONICAL_MANIFEST_MISMATCH")
    repair = manifest.get("targeted_audio_repair") or {}
    require(sha(video) == SEPARATE_ROOM_FINAL_SHA[kind]
            and repair.get("input_artifact_id") == 13813995846
            and repair.get("input_archive_sha256") == separate_room_repair.ARCHIVE_SHA
            and repair.get("input_qa_artifact_id") == 13815352755
            and repair.get("input_qa_sha256") == separate_room_repair.QA_JSON_SHA
            and repair.get("video_packets_preserved") is True
            and repair.get("outside_cut_pcm_preserved_before_aac_encode") is True
            and repair.get("video_packet_hashes_sha256") == SEPARATE_ROOM_PACKET_SHA[kind]
            and separate_room_repair.sha("\n".join(separate_room_repair.packet_hashes(video)).encode()) == SEPARATE_ROOM_PACKET_SHA[kind],
            "SEPARATE_ROOM_EXACT_AUDIO_REPAIR_MISMATCH")
    if kind == "overview":
        clarity = repair.get("final_clarity") or {}
        require(clarity.get("input_artifact_id") == 13815668134
                and clarity.get("input_archive_sha256") == separate_room_repair.CLARITY_ARCHIVE_SHA
                and clarity.get("old_text") == separate_room_repair.CLARITY_OLD
                and clarity.get("new_text") == separate_room_repair.CLARITY_NEW
                and clarity.get("video_packets_preserved") is True
                and clarity.get("outside_cut_pcm_preserved_before_aac_encode") is True
                and clarity.get("short_preserved_sha256") == SEPARATE_ROOM_FINAL_SHA["short"],
                "SEPARATE_ROOM_FINAL_CLARITY_MISMATCH")
    else:
        require(manifest.get("composition") == "native_full_frame_9_16_no_padding"
                and "final_clarity" not in repair,
                "SEPARATE_ROOM_UNCHANGED_NATIVE_SHORT_MISMATCH")


def validate_bundle(cfg, directory, kind):
    module = cfg["module"]
    slug, artifact_body_sha = module.SLUG, body_identity(cfg)
    research = cfg.get("research_path") or module.RESEARCH
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
            and manifest.get("content_sha256") == artifact_identity(cfg)
            and manifest.get("kind") == kind
            and manifest.get("media_item_id") == item_id(cfg, kind)
            and manifest.get("uploaded") is False and manifest.get("public") is False,
            "MANIFEST_IDENTITY_MISMATCH")
    require(manifest.get("source_file") == str(research.relative_to(ROOT)),
            "SOURCE_FILE_MISMATCH")
    video = directory / f"{kind}.mp4"
    wav = directory / f"{kind}-review-voice.wav"
    contact = directory / f"{kind}-visual-contact-sheet.jpg"
    frames = {f"{kind}-frame-{i:02d}.jpg": sha(directory / f"{kind}-frame-{i:02d}.jpg")
              for i in range(1, 9)}
    transcript = (directory / f"{kind}-asr.txt" if module in (positivity, productive, code7500, kindergarten, midyear, separate_room) else
                  root / "evidence" / f"{slug}--{kind}-descript-transcript.txt")
    require(sha(video) == manifest["video_sha256"]
            and sha(wav) == manifest["audio_sha256"] == evidence["audio_sha256"]
            and sha(contact) == manifest["contact_sha256"]
            and list(frames.values()) == manifest["frame_sha256"]
            and sha(research) == manifest["source_file_sha256"],
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
    if module is kindergarten:
        scripts = {k: list(v) for k, v in scripts.items()}
        scripts['overview'][-1] = scripts['overview'][-1].replace(kindergarten_repair.OLD, kindergarten_repair.NEW)
        independent = root / 'evidence' / f'{slug}--{kind}-descript-transcript.txt'
        require(sha(independent) == evidence.get('descript_transcript_sha256'),
                'KINDERGARTEN_INDEPENDENT_TRANSCRIPT_MISMATCH')
    if module is midyear:
        scripts = {k: list(v) for k, v in scripts.items()}
        scripts["overview"][-1] = scripts["overview"][-1].replace(midyear_cta.OLD, midyear_cta.NEW)
        scripts["short"].append(midyear_repair.CLOSING)
    expected_visuals = provenance["images"]
    if module is separate_room:
        scripts = {k: list(v) for k, v in scripts.items()}
        require(scripts["overview"][-1].count(separate_room_repair.CLARITY_OLD) == 1,
                "SEPARATE_ROOM_CLARITY_SOURCE_CHANGED")
        scripts["overview"][-1] = scripts["overview"][-1].replace(
            separate_room_repair.CLARITY_OLD, separate_room_repair.CLARITY_NEW)
        expected_visuals = [x for x in expected_visuals if x["scene"].startswith(kind + "-")]
        require(sha(directory / "asr-review.json") == SEPARATE_ROOM_ASR_SHA,
                "SEPARATE_ROOM_FINAL_ASR_EVIDENCE_MISMATCH")
    require(manifest["script_segments"] == scripts[kind]
            and manifest["visual_sources"] == expected_visuals,
            "REVIEWED_SOURCE_OR_VISUALS_CHANGED")
    module.verify_video(video, kind)
    if module is productive:
        validate_productive_repair(manifest, video, kind)
    if module is code7500:
        validate_7500_repair(manifest, video, kind)
    if module is kindergarten:
        validate_kindergarten_repair(manifest, video, kind)
    if module is midyear:
        validate_midyear_repair(manifest, video, kind)
    if module is separate_room:
        validate_separate_room_repair(manifest, video, kind)
    item = {
        "technical_verified": True, "source": {"slug": slug, "content_sha256": source_sha},
        "type": "video_overview" if kind == "overview" else "article_short",
        "id": item_id(cfg, kind), "final_sha256": sha(video),
        "manifest_sha256": sha(manifest_path), "transcript_sha256": sha(transcript),
        "visual_review_sha256": sha(contact), "source_file_sha256": sha(research),
        "frame_sha256": frames,
    }
    require_owner_media_quality(item, kind, approval_root=root)
    return video


def metadata(cfg, kind, overview_id=None):
    module = cfg["module"]
    description = (
        cfg.get("intro_by_kind", {}).get(kind, cfg["intro"]) + "\n\nלמאמר המלא והמקורות: " + module.ARTICLE
        + "\n\nקראו עוד באתר KESHER — שירה סהרוני."
        + "\nKESHER_OWNER_MEDIA_ITEM=" + item_id(cfg, kind)
        + "\nsource_slug=" + module.SLUG + "\ncontent_sha256=" + cfg["canonical_sha"]
        + "\nקריינות סינתטית: BlueTTS 2.5 (MIT), RenikudPlus (Apache 2.0), "
          "LibriTTS-R / Google LLC, דוברת 6147 (CC BY 4.0)."
        + "\nhttps://huggingface.co/notmax123/BlueTTS2.5-onnx"
        + "\nhttps://huggingface.co/notmax123/RenikudPlus"
        + "\nhttps://www.openslr.org/141/"
        + "\nhttps://creativecommons.org/licenses/by/4.0/"
        + (("\nתמונות: KESHER / Adobe Firefly; Pexels: MART PRODUCTION, Mizuno K, cottonbro studio."
             if kind == "overview" else "\nתמונות: Pexels, MART PRODUCTION ו-Mizuno K.")
           + "\nhttps://www.pexels.com/legal-pages/license"
           if module is separate_room else
           "\nתמונות מקוריות שנוצרו עבור KESHER באמצעות Adobe Firefly."
           if module in (positivity, productive, code7500, kindergarten, midyear) else "\nתמונות מקוריות שנוצרו עבור KESHER באמצעות OpenAI.")
    )
    if kind == "short":
        require(isinstance(overview_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", overview_id),
                "PUBLIC_OVERVIEW_REQUIRED_FIRST")
        description += ("\nלסרטון המלא בערוץ: https://www.youtube.com/watch?v=" + overview_id
                        + "\nאפשר לפתוח את הסרטון המלא בעמוד הערוץ אם הקישור אינו לחיץ ב-Shorts.")
    return {"title": cfg["titles"][kind], "description": description,
            "categoryId": "22", "tags": cfg.get("tags_by_kind", {}).get(kind, cfg["tags"]),
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
        relevant = (module.SLUG in desc or module.SOURCE_SHA in desc or cfg["canonical_sha"] in desc or body_identity(cfg) in desc
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


def deleted_upload_marker(row, playlist):
    """Recognize only YouTube's authenticated uploads-playlist tombstone."""
    snippet = row.get("snippet") or {}
    resource = snippet.get("resourceId") or {}
    video_id = (row.get("contentDetails") or {}).get("videoId")
    return (
        isinstance(video_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id)
        and snippet.get("channelId") == CHANNEL
        and snippet.get("playlistId") == playlist
        and resource.get("kind") == "youtube#video"
        and resource.get("videoId") == video_id
        and snippet.get("title") == "Deleted video"
        and not snippet.get("videoOwnerChannelId")
        and (row.get("status") or {}).get("privacyStatus") == "privacyStatusUnspecified"
    )


def confirm_deleted_upload(yt, playlist, video_id):
    """Require explicit API videoNotFound, not an empty or transient response."""
    try:
        yt.playlistItems().list(part="snippet,contentDetails,status",
                                playlistId=playlist, videoId=video_id,
                                maxResults=1).execute()
    except Exception as exc:
        if getattr(getattr(exc, "resp", None), "status", None) != 404:
            return False
        try:
            error = json.loads(exc.content)["error"]
            return error.get("code") == 404 and any(
                item.get("reason") == "videoNotFound"
                and item.get("domain") == "youtube.playlistItem"
                and item.get("location") == "videoId"
                for item in error.get("errors", [])
            )
        except (AttributeError, TypeError, ValueError, KeyError):
            return False
    return False


def scan_video_records(yt, ids, deleted_candidates=None, playlist=None):
    """Read all upload IDs, retry omitted batch records individually, fail closed.

    Processing details are needed only for final public verification, not for
    source dedup. A missing record is never treated as proof of absence.
    """
    records = {}
    require(len(ids) == len(set(ids)), "DUPLICATE_UPLOAD_PLAYLIST_ID")

    def collect(requested):
        rows = yt.videos().list(part="snippet,status", id=",".join(requested)).execute().get("items", [])
        for row in rows:
            vid = row.get("id")
            require(vid in requested and vid not in records, "UNEXPECTED_OR_DUPLICATE_VIDEO_RECORD")
            require((row.get("snippet") or {}).get("channelId") == CHANNEL, "UNEXPECTED_CHANNEL")
            records[vid] = row

    for i in range(0, len(ids), 50):
        collect(ids[i:i+50])
    missing = [vid for vid in ids if vid not in records]
    if missing:
        print("OWNER_DEDUP_BATCH_OMISSIONS " + str(len(missing)), flush=True)
        for vid in missing:
            collect([vid])
    missing = [vid for vid in ids if vid not in records]
    # Every ID is accounted for by a video record or a current, explicit
    # authenticated tombstone plus an independent exact-ID API 404 reason.
    deleted = set()
    for vid in missing:
        if playlist and vid in (deleted_candidates or set()) and confirm_deleted_upload(yt, playlist, vid):
            deleted.add(vid)
    missing = [vid for vid in missing if vid not in deleted]
    if deleted:
        print("OWNER_DEDUP_CONFIRMED_DELETED " + str(len(deleted)), flush=True)
    if missing:
        # Public repository logs must not expose private/unlisted video IDs.
        fingerprints = [hashlib.sha256(vid.encode()).hexdigest()[:12] for vid in missing]
        print("OWNER_DEDUP_UNRESOLVED " + json.dumps({
            "playlist_count": len(ids), "observed_count": len(records),
            "missing_count": len(missing), "missing_id_fingerprints": fingerprints,
        }), flush=True)
    require(not missing and set(records).isdisjoint(deleted)
            and set(records) | deleted == set(ids), "INCOMPLETE_VIDEO_DEDUP_SCAN")
    return [records[vid] for vid in ids if vid in records]


def scan(yt, cfg):
    rows = yt.channels().list(part="id,contentDetails", mine=True).execute().get("items", [])
    require(len(rows) == 1 and rows[0]["id"] == CHANNEL, "WRONG_YOUTUBE_CHANNEL")
    playlist = rows[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, seen_tokens, token = [], set(), None
    deleted_candidates = set()
    while True:
        page = yt.playlistItems().list(part="snippet,contentDetails,status", playlistId=playlist,
                                       maxResults=50, pageToken=token).execute()
        for row in page.get("items", []):
            vid = row["contentDetails"]["videoId"]
            ids.append(vid)
            if deleted_upload_marker(row, playlist):
                deleted_candidates.add(vid)
        token = page.get("nextPageToken")
        if not token:
            break
        require(token not in seen_tokens and len(seen_tokens) < 200, "INCOMPLETE_DEDUP_SCAN")
        seen_tokens.add(token)
    return classify(cfg, scan_video_records(yt, ids, deleted_candidates, playlist))


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
