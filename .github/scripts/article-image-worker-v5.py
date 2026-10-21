#!/usr/bin/env python3
"""Kesher trusted article image worker V5.

V5 keeps the V4 external-provider policy, but replaces the finite/off-topic
repository-curated terminal fallback with the already-approved LocalEditorial
contract. LocalEditorial renders an article-bound, deterministic, figurative
editorial illustration with unique pixels and no network/API dependency.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

V4_PATH = Path(__file__).with_name("article-image-worker-v4.py")
spec = importlib.util.spec_from_file_location("kesher_article_image_worker_v4", V4_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load image worker v4 from {V4_PATH}")
v4 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v4
spec.loader.exec_module(v4)

core = v4.core

WIDTH = 1200
HEIGHT = 675
PALETTES = (
    ("#F7F1E8", "#D9E7E4", "#577C7A", "#D99A73", "#4C5B61"),
    ("#F5F0EA", "#E4DDD0", "#6F8F87", "#C9856B", "#44545B"),
    ("#F8F2EA", "#DDE8EC", "#65829A", "#D89B74", "#4A5661"),
    ("#F4EFE8", "#E3E6D4", "#788C67", "#CE8D70", "#4E5956"),
    ("#F8F4EE", "#E8DFEA", "#817394", "#D59A77", "#50525E"),
    ("#F6F1EB", "#DFE7DC", "#68826F", "#CF9274", "#4A5954"),
    ("#F8F3EB", "#E2E4EE", "#6E7895", "#D39172", "#4C5665"),
    ("#F5F1EB", "#E6DED4", "#8B7466", "#D29A72", "#4F565A"),
)


def _slug(post: dict[str, Any]) -> str:
    return str(post.get("slug") or post.get("id") or "article").strip()


def _topic_text(post: dict[str, Any]) -> str:
    return " ".join(
        str(post.get(field) or "")
        for field in ("id", "slug", "title", "category", "subcategory", "excerpt")
    ).lower()


def _motif(post: dict[str, Any]) -> str:
    text = _topic_text(post)
    if any(token in text for token in ("גמילה", "חיתול", "טיטול", "קקי", "עצירות", "אסלה", "שירותים", "potty", "toilet", "constipation")):
        return "bathroom"
    if any(token in text for token in ("מעון", "גן", "מטפלת", "daycare", "kindergarten", "caregiver")):
        return "daycare"
    if any(token in text for token in ("כיתה א", "בית ספר", "school", "first-grade", "ילקוט")):
        return "school"
    if any(token in text for token in ("זוג", "נישוא", "דייט", "קשר", "relationship", "couple", "dating", "חתונה")):
        return "couples"
    if any(token in text for token in ("רילוקיישן", "הגירה", "relocation", "חזרה לארץ")):
        return "relocation"
    return "support"


def _palette(slug: str, variant: int) -> tuple[str, str, str, str, str]:
    digest = hashlib.sha256(f"{slug}|{variant}".encode("utf-8")).digest()
    return PALETTES[digest[0] % len(PALETTES)]


def _person(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float, skin: str, clothes: str, facing: int = 1) -> None:
    head = int(30 * scale)
    body_w = int(48 * scale)
    body_h = int(92 * scale)
    draw.ellipse((x - head, y - head, x + head, y + head), fill=skin)
    draw.rounded_rectangle(
        (x - body_w // 2, y + head - 4, x + body_w // 2, y + head + body_h),
        radius=max(8, int(16 * scale)),
        fill=clothes,
    )
    arm_y = y + head + int(36 * scale)
    draw.line((x, arm_y, x + facing * int(58 * scale), arm_y + int(14 * scale)), fill=clothes, width=max(5, int(11 * scale)))
    leg_y = y + head + body_h
    draw.line((x - int(12 * scale), leg_y, x - int(22 * scale), leg_y + int(70 * scale)), fill=clothes, width=max(5, int(12 * scale)))
    draw.line((x + int(12 * scale), leg_y, x + int(24 * scale), leg_y + int(70 * scale)), fill=clothes, width=max(5, int(12 * scale)))


def _draw_room(draw: ImageDraw.ImageDraw, bg: str, soft: str, line: str, variant: int) -> None:
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=bg)
    floor_y = 500 + (variant % 3) * 8
    draw.rectangle((0, floor_y, WIDTH, HEIGHT), fill=soft)
    draw.line((0, floor_y, WIDTH, floor_y), fill=line, width=3)
    for x in range(0, WIDTH, 150):
        draw.line((x, floor_y, x + 35, HEIGHT), fill=bg, width=2)


def _draw_bathroom(draw: ImageDraw.ImageDraw, palette: tuple[str, str, str, str, str], variant: int) -> str:
    bg, soft, accent, skin, line = palette
    _draw_room(draw, bg, soft, line, variant)
    # Bathroom details: mirror, towel, toilet and step stool.
    draw.rounded_rectangle((790, 115, 1030, 275), radius=28, fill="#EEF4F3", outline=accent, width=5)
    draw.rectangle((1060, 150, 1080, 340), fill=line)
    draw.rounded_rectangle((1020, 205, 1130, 300), radius=12, fill=accent)
    draw.rounded_rectangle((850, 315, 1035, 405), radius=18, fill="#FCFCF8", outline=line, width=5)
    draw.ellipse((830, 365, 1055, 485), fill="#FCFCF8", outline=line, width=5)
    draw.rounded_rectangle((890, 455, 1000, 540), radius=18, fill="#FCFCF8", outline=line, width=5)
    draw.rounded_rectangle((700, 470, 820, 525), radius=10, fill=accent)
    _person(draw, 310 + variant * 4, 260, 1.35, skin, line, facing=1)
    _person(draw, 535 + variant * 3, 335, 0.88, skin, accent, facing=1)
    # Join the interaction visually without text.
    draw.line((390, 350, 485, 375), fill=line, width=14)
    return "איור עריכתי מקומי של הורה וילד בחדר רחצה ביתי, לצד אסלה ושרפרף, באווירה רגועה ותומכת."


def _draw_daycare(draw: ImageDraw.ImageDraw, palette: tuple[str, str, str, str, str], variant: int) -> str:
    bg, soft, accent, skin, line = palette
    _draw_room(draw, bg, soft, line, variant)
    draw.rounded_rectangle((760, 130, 1080, 500), radius=22, fill="#FAFAF5", outline=accent, width=6)
    draw.rectangle((805, 210, 1035, 500), fill=soft, outline=line, width=4)
    for i, (x, y) in enumerate(((690, 430), (760, 390), (830, 445), (900, 405))):
        size = 55 + (i % 2) * 10
        draw.rounded_rectangle((x, y, x + size, y + size), radius=8, fill=(accent if i % 2 else line))
    _person(draw, 300 + variant * 3, 265, 1.3, skin, line, facing=1)
    _person(draw, 515 + variant * 2, 340, 0.85, skin, accent, facing=1)
    draw.line((380, 360, 465, 385), fill=line, width=13)
    return "איור עריכתי מקומי של הורה ופעוט בכניסה למסגרת ילדים, עם דלת פתוחה וקוביות משחק, ברגע פרידה תומך."


def _draw_school(draw: ImageDraw.ImageDraw, palette: tuple[str, str, str, str, str], variant: int) -> str:
    bg, soft, accent, skin, line = palette
    _draw_room(draw, bg, soft, line, variant)
    draw.rounded_rectangle((720, 210, 1080, 475), radius=18, fill="#FAFAF6", outline=line, width=5)
    draw.rectangle((770, 260, 1030, 300), fill=accent)
    draw.rectangle((770, 330, 980, 370), fill=line)
    draw.rounded_rectangle((610, 390, 720, 500), radius=20, fill=accent, outline=line, width=4)
    draw.arc((625, 350, 705, 430), 180, 360, fill=line, width=8)
    _person(draw, 285 + variant * 4, 260, 1.25, skin, line, facing=1)
    _person(draw, 500 + variant * 2, 335, 0.88, skin, accent, facing=1)
    return "איור עריכתי מקומי של הורה וילד בסביבה ביתית לקראת בית הספר, לצד ילקוט וספרים, באווירה רגועה ומעודדת."


def _draw_couples(draw: ImageDraw.ImageDraw, palette: tuple[str, str, str, str, str], variant: int) -> str:
    bg, soft, accent, skin, line = palette
    _draw_room(draw, bg, soft, line, variant)
    draw.rounded_rectangle((350, 430, 850, 535), radius=35, fill=soft, outline=line, width=4)
    draw.ellipse((535, 400, 665, 455), fill=accent)
    _person(draw, 390 + variant * 2, 280, 1.1, skin, line, facing=1)
    _person(draw, 805 - variant * 2, 280, 1.1, skin, accent, facing=-1)
    return "איור עריכתי מקומי של שני בני זוג יושבים זה מול זה בשיחה רגועה בבית, עם שפת גוף פתוחה וקשובה."


def _draw_relocation(draw: ImageDraw.ImageDraw, palette: tuple[str, str, str, str, str], variant: int) -> str:
    bg, soft, accent, skin, line = palette
    _draw_room(draw, bg, soft, line, variant)
    draw.rectangle((760, 270, 1010, 500), fill="#FAFAF6", outline=line, width=5)
    draw.polygon(((735, 280), (885, 155), (1035, 280)), fill=accent, outline=line)
    draw.rounded_rectangle((830, 375, 900, 500), radius=8, fill=soft, outline=line, width=4)
    draw.rounded_rectangle((570, 430, 690, 520), radius=12, fill=accent, outline=line, width=4)
    _person(draw, 300 + variant * 3, 275, 1.2, skin, line, facing=1)
    _person(draw, 485 + variant * 2, 315, 1.0, skin, accent, facing=1)
    return "איור עריכתי מקומי של זוג או משפחה לצד בית ומזוודה בתקופת מעבר, באווירה שממחישה שינוי והסתגלות."


def _draw_support(draw: ImageDraw.ImageDraw, palette: tuple[str, str, str, str, str], variant: int) -> str:
    bg, soft, accent, skin, line = palette
    _draw_room(draw, bg, soft, line, variant)
    draw.rounded_rectangle((720, 340, 1020, 500), radius=28, fill=soft, outline=line, width=4)
    draw.ellipse((810, 285, 925, 390), fill=accent)
    _person(draw, 330 + variant * 3, 280, 1.2, skin, line, facing=1)
    _person(draw, 535 + variant * 2, 340, 0.9, skin, accent, facing=1)
    return "איור עריכתי מקומי של מבוגר וילד באינטראקציה ביתית תומכת, בסביבה רגועה שמתאימה לתוכן הדרכת הורים."


def render_local_editorial(post: dict[str, Any], variant: int) -> tuple[bytes, str]:
    slug = _slug(post)
    palette = _palette(slug, variant)
    image = Image.new("RGB", (WIDTH, HEIGHT), palette[0])
    draw = ImageDraw.Draw(image)
    motif = _motif(post)
    renderer = {
        "bathroom": _draw_bathroom,
        "daycare": _draw_daycare,
        "school": _draw_school,
        "couples": _draw_couples,
        "relocation": _draw_relocation,
        "support": _draw_support,
    }[motif]
    visual_match = renderer(draw, palette, variant)

    # Article/variant-bound micro details keep pixels unique without adding text
    # or weakening the visual semantics.
    digest = hashlib.sha256(f"{slug}|{variant}|local-editorial-v1".encode("utf-8")).digest()
    accent = palette[2]
    for index in range(6):
        x = 65 + digest[index] * 3
        y = 70 + digest[index + 6] % 90
        radius = 5 + digest[index + 12] % 7
        draw.ellipse((x, y, x + radius, y + radius), fill=accent)

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue(), visual_match


def local_editorial_fallback(
    repo: str,
    post: dict[str, Any],
    head_ref: str,
    token: str,
    attempts: list[str],
    *args: Any,
    existing_hashes: set[str] | None = None,
    **kwargs: Any,
) -> core.ImageCandidate | None:
    del repo, head_ref, token, args, kwargs
    existing_hashes = set(existing_hashes or set())
    slug = _slug(post)
    start = hashlib.sha256(slug.encode("utf-8")).digest()[0] % 8
    for offset in range(8):
        variant = (start + offset) % 8
        data, visual_match = render_local_editorial(post, variant)
        if core.candidate_is_duplicate(data, existing_hashes):
            continue
        attempts[:] = ["local-editorial"]
        print(
            f"IMAGE_LOCAL_EDITORIAL_READY slug={slug} variant={variant} unique=yes",
            file=sys.stderr,
            flush=True,
        )
        return core.ImageCandidate(
            "LocalEditorial",
            data,
            "png",
            f"local-editorial://{slug}/{variant}",
            visual_match,
            attempts.copy(),
        )
    print(
        f"IMAGE_LOCAL_EDITORIAL_EXHAUSTED slug={slug} variants=8",
        file=sys.stderr,
        flush=True,
    )
    return None


# V4's choose_candidate resolves the module-global local_fallback at call time,
# so this replaces only the terminal no-network provider while preserving all
# bounded external attempts and duplicate-pixel checks.
v4.local_fallback = local_editorial_fallback
v4.v3.local_fallback = local_editorial_fallback


def main() -> int:
    return v4.main()


if __name__ == "__main__":
    raise SystemExit(main())
