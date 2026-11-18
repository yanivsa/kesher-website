#!/usr/bin/env python3
"""One-off, fail-closed replacement of the 17 financial-guidance SVG heroes.

The existing trusted GitHub image worker generates photographs and verifies
the *pixels* against the individual article. Nothing is written unless all
remaining legacy heroes have passed verification and uniqueness checks.
This script does not publish or modify the article text, slug, date or author.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
POSTS = ROOT / "src/data/financialGuidancePosts.json"
DIMENSIONS = ROOT / "src/data/imageDimensions.ts"
MIGRATION = ROOT / "config/financial-hero-migration.json"
IMAGE_ROOT = ROOT / "public/images/generated/blog"
WORKER = ROOT / ".github/scripts/article-image-worker-v4.py"

# Each image must depict an article-specific real-life moment. This is part of
# both the generator prompt and the model's independent pixel-verification brief.
SCENES = {
    "financial-secrecy-couples": "Two adult partners at a kitchen table reviewing an unexpected bill together; one concerned and the other listening, conveying difficult but respectful financial disclosure.",
    "unequal-income-fair-budget": "Two adult partners comparing separate pay slips and a shared household budget at home, actively discussing fair contributions without arguing.",
    "couples-joint-or-separate-accounts": "Two adult partners thoughtfully comparing two account statements and one shared household notebook at a kitchen table, deciding how to organize finances.",
    "weekly-money-conversation": "Two adult partners having a calm scheduled weekly budget discussion at home with an open blank notebook, pens and two mugs, with phones put away.",
    "financial-boundaries-couples": "Two adult partners openly discussing personal spending and shared financial boundaries at a kitchen table, each with a notebook, calm and equal body language.",
    "family-budget-guide": "An adult couple organizing household bills, receipts and a household budget notebook together on a dining table in a realistic family home.",
    "tracking-family-expenses": "A pair of adult hands sorting everyday grocery and utility receipts into a household budgeting notebook on a kitchen table, realistic paper objects and calculator.",
    "good-income-negative-balance": "Two worried but composed adults in a real family kitchen reviewing a stack of bills and their bank budget notes, recognizing a cash-flow shortfall.",
    "annual-family-expenses": "A parent planning irregular school, holiday and household expenses using a yearly paper calendar and budget notebook in a lived-in kitchen.",
    "variable-income-family-budget": "A self-employed adult at a home desk comparing invoices from different months with a household budget notebook, portraying variable monthly income.",
    "income-expense-gap-first-steps": "Two adult partners calmly sorting urgent household bills and a simple expense list at their kitchen table, prioritizing what must be paid.",
    "talking-money-with-kids-by-age": "A parent teaching a school-age child the difference between needs and wants using everyday coins and a shopping list at home, a warm learning moment.",
    "allowance-kids-guide": "A parent and school-age child choosing how to divide allowance coins into savings and spending jars at a home table, natural candid interaction.",
    "child-purchase-demands-boundaries": "A parent gently talking to a school-age child in a real grocery store aisle about choosing one affordable purchase within their family budget rather than everything on the shelf.",
    "children-family-budget-participation": "A parent involving two school-age children in choosing a family outing within their household budget using a paper list of options at the kitchen table, reassuring atmosphere.",
    "planning-budget-new-baby": "New parents planning baby expenses at home with baby clothes, diapers and a notebook on the table, and a crib in the background.",
    "dealing-with-income-drop-as-family": "Two adult partners at home compassionately reviewing a reduced-income situation with a paper budget and laptop closed nearby, showing mutual support.",
}


def load_trusted_worker():
    spec = importlib.util.spec_from_file_location("financial_hero_trusted_worker", WORKER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Trusted image worker unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def legacy_image(post: dict) -> bool:
    pid = str(post.get("id") or "")
    return post.get("image") == f"/images/financial-guidance/articles/{pid}.svg"


def audit_posts(posts: list[dict]) -> list[dict]:
    ids = [p.get("id") for p in posts]
    if len(posts) != 17 or len(set(ids)) != 17 or set(ids) != set(SCENES):
        raise RuntimeError("The original 17-article financial cohort changed; review the migration before retrying")
    for post in posts:
        pid = post["id"]
        image = str(post.get("image") or "")
        if not legacy_image(post) and not re.fullmatch(
            rf"/images/generated/blog/{re.escape(pid)}-financial-hero-[0-9a-f]{{12}}\.(?:jpg|png)",
            image,
        ):
            raise RuntimeError(f"Unexpected financial hero reference for {pid}: {image}")
    return [p for p in posts if legacy_image(p)]


def main() -> int:
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    remaining = audit_posts(posts)
    print(f"FINANCIAL_HERO_AUDIT total={len(posts)} legacy={len(remaining)} verified={len(posts)-len(remaining)}", flush=True)
    if not remaining:
        return 0

    worker = load_trusted_worker()
    if not worker.v3.google_key():
        raise RuntimeError("GOOGLE_API_KEY/GEMINI_API_KEY needed for actual pixel verification; no image substitutions made")

    existing_hashes = worker.collect_existing_hashes(ROOT)
    prepared: list[tuple[dict, bytes, str, int, int, str, str, str]] = []

    for index, post in enumerate(remaining, start=1):
        pid = post["id"]
        contextual_post = dict(post)
        contextual_post["excerpt"] = (
            "Required specific photographic financial editorial scene: "
            + SCENES[pid] + " Original article: " + str(post.get("excerpt") or "")[:180]
        )
        attempts: list[str] = []
        candidate = worker.try_gemini_variants(
            contextual_post, attempts, existing_hashes=existing_hashes, generation_limit=2
        )
        # Both stock providers use the exact same independent Gemini pixel verifier.
        if candidate is None:
            candidate = worker.v3.try_pexels(contextual_post, attempts, existing_hashes=existing_hashes)
        if candidate is None:
            candidate = worker.try_pixabay(contextual_post, attempts, existing_hashes=existing_hashes)
        if candidate is None:
            raise RuntimeError(f"FAILED_CLOSED id={pid} attempts={attempts}; no partial write")

        width, height, ext = worker.core.validate_candidate(candidate.data)
        digest = hashlib.sha256(candidate.data).hexdigest()
        pixels = "pixels:" + worker.core.image_pixel_sha256(candidate.data)
        if digest in existing_hashes or pixels in existing_hashes:
            raise RuntimeError(f"Duplicate hero rejected: {pid}")
        existing_hashes.add(digest)
        existing_hashes.add(pixels)
        if not re.search(r"[\u0590-\u05FF]", candidate.visual_match) or len(candidate.visual_match) < 30:
            raise RuntimeError(f"Missing trusted Hebrew visual description: {pid}")
        dest = f"/images/generated/blog/{pid}-financial-hero-{digest[:12]}.{ext}"
        if (ROOT / "public" / dest.lstrip("/")).exists():
            raise RuntimeError(f"Refusing to overwrite existing generated asset: {dest}")
        prepared.append((
            post, candidate.data, dest, width, height,
            candidate.visual_match, candidate.provider, candidate.source_url,
        ))
        print(f"FINANCIAL_HERO_VERIFIED {index}/{len(remaining)} id={pid} provider={candidate.provider} {width}x{height}", flush=True)

    # Apply all 17 changes together, rather than leaving any half-migrated
    # article if an API provider or verifier fails on a later image.
    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
    dims = DIMENSIONS.read_text(encoding="utf-8")
    inserted = []
    for post, data, url, width, height, alt, provider, source_url in prepared:
        (ROOT / "public" / url.lstrip("/")).write_bytes(data)
        post["image"] = url
        post["imageAlt"] = alt
        post["imageProvider"] = provider
        post["imageSourceUrl"] = source_url
        post["imageCredit"] = (
            "תמונת מערכת מקורית שנוצרה עבור אתר קשר"
            if provider == "Gemini" else f"צילום ממאגר {provider}, בתנאי הרישיון הרלוונטיים"
        )
        post["imageIsFallback"] = provider != "Gemini"
        post["imageVerified"] = True
        inserted.append(f"  '{url}': {{ width: {width}, height: {height} }},")
    marker = "const dimensions: Record<string, { width: number; height: number }> = {"
    if dims.count(marker) != 1:
        raise RuntimeError("Unexpected imageDimensions.ts format")
    dims = dims.replace(marker, marker + "\n" + "\n".join(inserted), 1)
    DIMENSIONS.write_text(dims, encoding="utf-8")
    POSTS.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    migration = json.loads(MIGRATION.read_text(encoding="utf-8"))
    migration["legacy_svg_ids"] = []
    MIGRATION.write_text(json.dumps(migration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"FINANCIAL_HERO_REPAIR_COMPLETE generated={len(prepared)} remaining=0", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
