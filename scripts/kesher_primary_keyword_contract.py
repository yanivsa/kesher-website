#!/usr/bin/env python3
"""Permanent repo-wide Primary Keyword contract and fail-closed validator for Jules articles."""

from __future__ import annotations

import html
import re
from typing import Any

# Canonical semantic English stems for Kesher therapeutic, parenting, and relationship topics
SEMANTIC_KEYWORD_DICTIONARY: dict[str, set[str]] = {
    # Potty training / Toddler transitions (requires potty/toilet/diaper concepts, generic training alone forbidden)
    "גמילה מטיטול": {"potty", "toilet", "diaper"},
    "גמילה מטיטולים": {"potty", "toilet", "diaper"},
    "גמילה מחיתולים": {"potty", "toilet", "diaper"},
    "גמילה מחיתול": {"potty", "toilet", "diaper"},
    "גמילת לילה": {"night", "potty", "bedwetting", "diaper"},
    # Pacifier weaning / Toddler transitions
    "גמילה ממוצץ": {"pacifier", "weaning", "soother", "dummy"},
    "גמילה ממוצצים": {"pacifier", "weaning", "soother", "dummy"},
    "מוצץ": {"pacifier", "soother", "dummy"},
    "מוצצים": {"pacifier", "soother", "dummy"},
    "גמילה מבקבוק": {"bottle", "weaning"},
    "גמילה מהנקה": {"breastfeeding", "nursing", "weaning"},
    # Separation anxiety
    "חרדת נטישה": {"separation", "anxiety"},
    "חרדת פרידה": {"separation", "anxiety"},
    # Daycare, Nursery & Early Childhood Transitions
    "מעבר ממטפלת למעון": {"caregiver", "daycare", "nursery", "transition"},
    "מעבר למעון": {"daycare", "nursery", "transition"},
    "מעבר לפעוטון": {"toddler", "daycare", "nursery", "transition"},
    "הסתגלות למעון": {"daycare", "nursery", "adaptation", "transition"},
    "הסתגלות לפעוטון": {"toddler", "daycare", "nursery", "adaptation", "transition"},
    "מעבר לגן": {"kindergarten", "preschool", "daycare", "transition"},
    "מעבר גן באמצע שנה": {"kindergarten", "preschool"},
    "הסתגלות לגן": {"kindergarten", "preschool", "adaptation", "transition"},
    "מעבר למיטת מעבר": {"toddler", "bed", "crib", "transition"},
    "מעבר לחדר נפרד": {"separate", "room", "baby", "transition"},
    # Gifted children / Education
    "ילד מחונן": {"gifted", "child", "giftedness"},
    "ילדים מחוננים": {"gifted", "children", "giftedness"},
    "מחוננות": {"gifted", "giftedness"},
    "רגישות רגשית": {"sensitivity", "emotional", "sensitive"},
    # Couples & Marriage
    "ייעוץ זוגי": {"couples", "counseling", "therapy", "marriage", "relationship"},
    "טיפול זוגי": {"couples", "counseling", "therapy", "marriage", "relationship"},
    "זוגיות": {"relationship", "couples", "marriage", "partner"},
    "משבר בזוגיות": {"crisis", "couples", "relationship", "marriage"},
    "משבר זוגי": {"crisis", "couples", "relationship", "marriage"},
    "ריבים בזוגיות": {"fights", "arguments", "conflict", "couples"},
    "תקשורת זוגית": {"communication", "couples", "conversation"},
    "בגידה": {"infidelity", "affair", "cheating", "betrayal"},
    "שיקום אמון": {"trust", "repair", "infidelity"},
    "שחיקה בזוגיות": {"burnout", "wear", "couples", "relationship"},
    "הכנה לנישואין": {"premarital", "wedding", "marriage"},
    "נישואין": {"marriage", "wedding"},
    # Singles & Dating
    "דייטים": {"dating", "dates", "relationship"},
    "מציאת זוגיות": {"finding", "relationship", "dating", "love"},
    "רווקות מאוחרת": {"late", "singleness", "singles"},
    "רווקות": {"singleness", "singles", "single"},
    "פחד מדחייה": {"fear", "rejection", "dating"},
    "בדידות": {"loneliness", "alone"},
    # Parenting & Child development
    "הדרכת הורים": {"parenting", "guidance", "parents"},
    "הנחיית הורים": {"parenting", "guidance", "parents"},
    "סמכות הורית": {"authority", "parental", "parenting"},
    "גבולות לילדים": {"boundaries", "limits", "discipline", "children"},
    "הצבת גבולות": {"boundaries", "limits", "setting"},
    "התקפי זעם": {"tantrums", "meltdowns", "anger"},
    "התקף זעם": {"tantrum", "meltdown", "anger"},
    "שיתוף פעולה": {"cooperation", "listening"},
    "ילד לא מקשיב": {"listening", "defiance", "arguing"},
    "משא ומתן עם ילדים": {"negotiation", "arguing", "boundaries"},
    "קשב וריכוז": {"adhd", "attention", "focus"},
    "הפרעת קשב": {"adhd", "attention"},
    "התארגנות בוקר": {"morning", "routine", "adhd"},
    "שגרת שינה": {"sleep", "bedtime", "routine"},
    "בעיות שינה": {"sleep", "problems", "insomnia"},
    "מריבות בין אחים": {"siblings", "rivalry", "fights"},
    # Toddler soiling accidents (poop in pants)
    "ילד עושה קקי במכנסיים": {"poop", "pooping", "soiling", "accident"},
    # Aliyah & Relocation
    "רילוקיישן": {"relocation", "moving", "transition"},
    "עלייה": {"aliyah", "immigration"},
    "זוגיות ברילוקיישן": {"relocation", "couples", "relationship"},
}

HEBREW_PREFIXES = (
    "", "ו", "ה", "ב", "כ", "ל", "מ", "ש",
    "וה", "וב", "ול", "וכ", "ומ",
    "כש", "מש", "שב", "של", "שה",
)


def normalize_hebrew_text(text: str) -> str:
    """Normalize Hebrew text: strip HTML, niqqud, normalize punctuation/quotes/dashes."""
    if not text:
        return ""
    # Strip HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = html.unescape(cleaned)
    # Strip niqqud
    cleaned = re.sub(r"[\u05b0-\u05c7]", "", cleaned)
    # Normalize quotes (״, ", ', ׳)
    cleaned = re.sub(r'["״״‟„“]', '"', cleaned)
    cleaned = re.sub(r"['׳`’‘]", "'", cleaned)
    # Normalize dashes (־, –, —, -)
    cleaned = re.sub(r"[־–—―]", "-", cleaned)
    # Normalize punctuation spacing
    cleaned = re.sub(r"[?!.,:;()\[\]{}]+", " ", cleaned)
    # Normalize whitespace
    return " ".join(cleaned.split()).strip()


def matches_keyword(text: str, keyword: str) -> bool:
    """Check if normalized text contains the keyword or a close Hebrew prefix variant."""
    norm_text = normalize_hebrew_text(text).lower()
    norm_kw = normalize_hebrew_text(keyword).lower()
    if not norm_text or not norm_kw:
        return False

    # Exact normalized substring match
    if norm_kw in norm_text:
        return True

    # Check Hebrew prefix variants on the first word of the keyword
    kw_words = norm_kw.split()
    first_word = kw_words[0]
    rest = " ".join(kw_words[1:])

    for prefix in HEBREW_PREFIXES:
        if not prefix:
            continue
        variant_first = prefix + first_word
        variant_kw = f"{variant_first} {rest}".strip() if rest else variant_first
        if variant_kw in norm_text:
            return True

    return False


def extract_first_paragraph(content: str) -> str:
    """Extract first visible paragraph from HTML content."""
    if not content:
        return ""
    match = re.search(r"<p(?:\s[^>]*)?>(.*?)</p>", content, re.I | re.S)
    if match:
        return match.group(1).strip()
    # Fallback to text before first header or double newline
    parts = re.split(r"<h[1-6]|<hr|\n\s*\n", content, flags=re.I)
    return parts[0].strip() if parts else ""


def keyword_in_opening(first_paragraph_html: str, keyword: str, max_words: int = 25) -> bool:
    """Verify that keyword appears in opening sentence or first ~20-25 words."""
    if not first_paragraph_html:
        return False

    # Strip HTML tags and decode entities while preserving punctuation
    clean_para = re.sub(r"<[^>]+>", " ", first_paragraph_html)
    clean_para = html.unescape(clean_para).strip()
    if not clean_para:
        return False

    # Check first sentence (split on sentence terminators: . ! ?)
    # Only treat as opening sentence if it is reasonably concise (<= 30 words)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean_para) if s.strip()]
    if sentences:
        first_sentence = sentences[0]
        if len(first_sentence.split()) <= 30 and matches_keyword(first_sentence, keyword):
            return True

    # Check first max_words of the paragraph
    norm_para = normalize_hebrew_text(clean_para)
    words = norm_para.split()
    opening_words = " ".join(words[:max_words])
    return matches_keyword(opening_words, keyword)


def parse_owner_required_keyword(topic_brief: str) -> str | None:
    """Extract required primary keyword from owner topic brief if specified."""
    if not topic_brief:
        return None
    for line in topic_brief.splitlines():
        match = re.match(
            r"^\s*(?:[-*]\s*)?(?:Required\s+)?Primary\s+Keyword\s*:\s*(.*?)\s*$",
            line,
            re.I,
        )
        if match and match.group(1).strip():
            return match.group(1).strip()
    return None


def parse_owner_semantic_stems(topic_brief: str) -> set[str] | None:
    """Extract optional trusted semantic stems from owner topic brief if specified."""
    if not topic_brief:
        return None
    for line in topic_brief.splitlines():
        match = re.match(
            r"^\s*(?:[-*]\s*)?(?:Trusted\s+|Semantic\s+)?(?:Stems|Concepts)\s*:\s*(.*?)\s*$",
            line,
            re.I,
        )
        if match and match.group(1).strip():
            stems = {s.strip().lower() for s in re.split(r"[,;|\s]+", match.group(1).strip()) if s.strip()}
            if stems:
                return stems
    return None


def slug_represents_keyword(slug: str, keyword: str, *, trusted_stems: set[str] | None = None) -> tuple[bool, str]:
    """Verify that slug is valid kebab-case and semantically maps to the Primary Keyword."""
    clean_slug = str(slug or "").strip().lower()
    if not clean_slug:
        return False, "Slug is missing or empty"
    if not re.fullmatch(r"^[a-z0-9]+(-[a-z0-9]+)*$", clean_slug):
        return False, f"Slug '{clean_slug}' is not valid kebab-case English"

    norm_kw = normalize_hebrew_text(keyword).lower()
    slug_tokens = set(clean_slug.split("-"))

    # 1. Explicit trusted stems if supplied
    if trusted_stems:
        if any(stem in slug_tokens or any(stem in token for token in slug_tokens) for stem in trusted_stems):
            return True, ""
        return False, (
            f"Slug '{clean_slug}' does not contain trusted semantic concepts "
            f"for '{keyword}' (expected one of: {sorted(trusted_stems)})"
        )

    # 2. Direct dictionary match
    expected_stems = SEMANTIC_KEYWORD_DICTIONARY.get(norm_kw)
    if expected_stems:
        if any(stem in slug_tokens or any(stem in token for token in slug_tokens) for stem in expected_stems):
            return True, ""
        return False, (
            f"Slug '{clean_slug}' does not contain expected semantic concepts "
            f"for '{keyword}' (expected one of: {sorted(expected_stems)})"
        )

    # 3. Check partial dictionary matches (sub-phrase matching)
    for dict_kw, stems in SEMANTIC_KEYWORD_DICTIONARY.items():
        if dict_kw in norm_kw or norm_kw in dict_kw:
            if any(stem in slug_tokens or any(stem in token for token in slug_tokens) for stem in stems):
                return True, ""

    # Unknown Primary Keyword without trusted semantic mapping: fail closed
    return False, f"Slug '{clean_slug}' could not be semantically verified: unknown keyword '{keyword}' has no trusted semantic mapping"


def exact_field(body: str, label: str) -> str | None:
    """Extract single-occurrence audit field value from PR body or text."""
    pattern = re.compile(rf"^\s*(?:[-*]\s*)?{re.escape(label)}\s*:\s*(.*?)\s*$", re.I)
    values = [
        match.group(1).strip()
        for line in (body or "").splitlines()
        if (match := pattern.match(line))
    ]
    return values[0] if len(values) == 1 and values[0] else None


def validate_primary_keyword_contract(
    post: dict[str, Any],
    pr_body: str = "",
    *,
    owner_topic_brief: str = "",
) -> list[str]:
    """Fail-closed GitHub validation gate for the Primary Keyword contract.

    Fails if:
    - Primary Keyword audit field missing from PR body / metadata
    - Owner topic brief specified a Required Primary Keyword that was not used
    - Primary Keyword missing from title/H1
    - Primary Keyword missing from first paragraph opening
    - Slug does not represent declared keyword
    - Resulting article URL does not use expected slug
    """
    errors: list[str] = []
    if not isinstance(post, dict):
        return ["Article post object must be a dictionary"]

    # 1. Extract declared Primary Keyword
    keyword = exact_field(pr_body, "Primary Keyword")
    if not keyword:
        keyword = str(post.get("primaryKeyword") or "").strip()
    if not keyword:
        # Check if Primary Search Query exists as fallback
        psq = exact_field(pr_body, "Primary Search Query") or str(post.get("primarySearchQuery") or "").strip()
        if psq:
            keyword = psq
        else:
            errors.append("Article PR is missing required 'Primary Keyword' audit field")
            return errors

    # 2. Verify against Owner Topic Brief requirement if present
    required_kw = parse_owner_required_keyword(owner_topic_brief)
    if not required_kw:
        # Check trusted repository environment/metadata if not passed directly
        import os
        trusted_env_brief = os.environ.get("KESHER_ARTICLE_TOPIC_BRIEF", "").strip()
        if not trusted_env_brief and os.environ.get("KESHER_ARTICLE_TOPIC_BRIEF_FILE", "").strip():
            try:
                from pathlib import Path
                p = Path(os.environ["KESHER_ARTICLE_TOPIC_BRIEF_FILE"].strip())
                if p.is_file():
                    trusted_env_brief = p.read_text(encoding="utf-8").strip()
            except OSError:
                pass
        required_kw = parse_owner_required_keyword(trusted_env_brief)
    trusted_stems = parse_owner_semantic_stems(owner_topic_brief)
    if not trusted_stems and 'trusted_env_brief' in locals():
        trusted_stems = parse_owner_semantic_stems(trusted_env_brief)

    if required_kw:
        norm_req = normalize_hebrew_text(required_kw).lower()
        norm_decl = normalize_hebrew_text(keyword).lower()
        if norm_req != norm_decl:
            errors.append(
                f"Declared Primary Keyword '{keyword}' does not match required owner keyword '{required_kw}'"
            )

    # 3. Title / H1 check
    title = str(post.get("title") or "").strip()
    if not title:
        errors.append("Article title is missing")
    elif not matches_keyword(title, keyword):
        errors.append(f"Primary Keyword '{keyword}' is missing from article title / H1: '{title}'")

    # 4. First paragraph opening check
    content = str(post.get("content") or "")
    first_p = extract_first_paragraph(content)
    if not first_p:
        errors.append("Article has no first paragraph in content")
    elif not keyword_in_opening(first_p, keyword):
        errors.append(
            f"Primary Keyword '{keyword}' must appear in the first paragraph opening sentence or first 25 words"
        )

    # 5. Slug semantic representation check
    slug = str(post.get("slug") or post.get("id") or "").strip()
    if not slug:
        errors.append("Article slug is missing")
    else:
        # Article/PR-controlled semantic-token fields are not trusted. Unknown keywords
        # fail closed until a repository-controlled mapping is added.
        valid_slug, slug_msg = slug_represents_keyword(slug, keyword, trusted_stems=trusted_stems)
        if not valid_slug:
            errors.append(slug_msg)

    # 6. Canonical URL matches slug
    source = post.get("source") or {}
    canonical_url = str(post.get("canonicalUrl") or source.get("canonical_url") or "").strip()
    if canonical_url:
        expected_url = f"/blog/{slug}"
        if not canonical_url.endswith(expected_url) and canonical_url != expected_url:
            errors.append(
                f"Article canonical URL '{canonical_url}' does not use the expected slug '{expected_url}'"
            )

    # 7. Meta / Browser title alignment if present
    meta_title = str(post.get("metaTitle") or post.get("seoTitle") or "").strip()
    if meta_title and not matches_keyword(meta_title, keyword):
        errors.append(
            f"Primary Keyword '{keyword}' is missing from SEO/meta title: '{meta_title}'"
        )

    return errors
