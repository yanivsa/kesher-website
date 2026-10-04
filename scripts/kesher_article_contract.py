from __future__ import annotations

import hashlib
import io
import json
import re
import warnings
from collections.abc import Iterable

ARTICLE_PUBLICATION_PATHS = frozenset(
    {
        "src/data/posts.json",
        "src/data/postSummaries.json",
        "public/sitemap.xml",
        "public/rss.xml",
        "public/llms.txt",
        "public/llms-full.txt",
    }
)

ARTICLE_IMAGE_PREFIX = "public/images/generated/blog/"


def normalize_repo_path(path: str) -> str:
    normalized = str(path or "").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def is_article_publication_path(path: str) -> bool:
    normalized = normalize_repo_path(path)
    if not normalized or any(part in {"", ".", ".."} for part in normalized.split("/")):
        return False
    return normalized in ARTICLE_PUBLICATION_PATHS or normalized.startswith(
        ARTICLE_IMAGE_PREFIX
    )


def forbidden_article_paths(paths: Iterable[str]) -> list[str]:
    return [
        normalize_repo_path(path)
        for path in paths
        if normalize_repo_path(path) and not is_article_publication_path(path)
    ]


# One contract for the producer, readiness checks and independent merge gate.
# Pipeline version remains 2: the binding fields make its evidence explicit.
IMAGE_PROVIDER_RULES = {
    "Gemini": ("generated", "gemini"),
    "Pixabay": ("stock", "pixabay"),
    "Pexels": ("stock", "pexels"),
    "Local": ("local_fallback", "local-curated"),
    "LocalEditorial": ("local_fallback", "local-editorial"),
}
IMAGE_PROVIDER_ORDER = ("gemini-1", "gemini-2", "gemini-3", "pexels", "pixabay", "local-curated")
IMAGE_EVIDENCE_FIELDS = (
    "Image Pipeline Version", "Image Provider", "Image Attempt Chain",
    "Image Generation Result", "Image Source URL", "Image SHA-256",
    "Image Dimensions", "Image Visual Match", "Image Article ID",
    "Image Article SHA-256", "Image Evidence Head",
)


def exact_field(body: str, label: str) -> str | None:
    pattern = re.compile(rf"^\s*(?:[-*]\s*)?{re.escape(label)}\s*:\s*(.*?)\s*$", re.I)
    values = [match.group(1).strip() for line in (body or "").splitlines()
              if (match := pattern.match(line))]
    return values[0] if len(values) == 1 else None


def article_sha256(post: dict) -> str:
    # Includes image path/alt and the complete editorial record. JSON formatting
    # changes do not invalidate pixels; any article field change does.
    data = json.dumps(post, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def image_dimensions(data: bytes) -> tuple[int, int]:
    """Return dimensions only after strict structure and full pixel decoding."""
    try:
        from PIL import Image, ImageFile
    except ImportError as exc:
        raise ValueError("image decoder unavailable; install requirements-article.txt") from exc
    if ImageFile.LOAD_TRUNCATED_IMAGES:
        raise ValueError("strict image decoder unavailable: truncated images enabled")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=["PNG", "JPEG"]) as image:
                # Pillow verifies PNG chunk CRCs up to, but excluding, IEND.
                # Require its complete, zero-length closing chunk and checksum.
                # Existing published PNGs may have inert zero padding after
                # IEND. Other trailing bytes remain a structural refusal.
                if image.format == "PNG" and not data.rstrip(b"\0").endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"):
                    raise ValueError("invalid PNG closing chunk")
                image.verify()
            # verify() checks structure without decoding pixels; reopen and
            # force every frame through the decoder before trusting dimensions.
            with Image.open(io.BytesIO(data), formats=["PNG", "JPEG"]) as image:
                dimensions = image.size
                for frame in range(getattr(image, "n_frames", 1)):
                    image.seek(frame)
                    image.load()
                return dimensions
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValueError(f"unsupported or malformed image: {exc}") from exc


def image_pixel_sha256(data: bytes) -> str:
    """Content identity survives recompression, metadata changes and file aliases."""
    image_dimensions(data)
    from PIL import Image
    fingerprint = hashlib.sha256()
    with Image.open(io.BytesIO(data)) as image:
        fingerprint.update(json.dumps([image.size, getattr(image, 'n_frames', 1)]).encode())
        for frame in range(getattr(image, 'n_frames', 1)):
            image.seek(frame)
            fingerprint.update(image.convert('RGBA').tobytes())
    return fingerprint.hexdigest()


def image_proof_errors(post: dict, body: str, head_sha: str, data: bytes | None = None,
                       *, require_head: bool = True) -> list[str]:
    import hashlib
    errors = []
    proof = {label: exact_field(body, label) for label in IMAGE_EVIDENCE_FIELDS}
    image = str(post.get("image") or "")
    if not image.startswith("/images/generated/blog/") or any(part in {".", "..", ""} for part in image.split("/")[1:]):
        errors.append("New article requires a trusted local image; no-image publication is forbidden")
    if len(str(post.get("imageAlt") or "")) < 20:
        errors.append("Image-bearing article requires concrete imageAlt text")
    if proof["Image Pipeline Version"] != "2":
        errors.append("Committed image requires Image Pipeline Version: 2")
    provider = proof["Image Provider"]
    rule = IMAGE_PROVIDER_RULES.get(provider)
    if rule is None:
        errors.append("Committed image requires a trusted Image Provider")
    else:
        result, last_attempt = rule
        if proof["Image Generation Result"] != result:
            errors.append(f"{provider} image must record {result} result")
        chain = (proof["Image Attempt Chain"] or "").split("/")
        expected = [list(IMAGE_PROVIDER_ORDER[:index + 1]) for index, value in enumerate(IMAGE_PROVIDER_ORDER)
                    if value.startswith("gemini-") and provider == "Gemini" or value == last_attempt]
        if chain not in expected:
            errors.append("Image Attempt Chain must truthfully begin with gemini and record provider fallthrough")
    source = proof["Image Source URL"] or ""
    if provider == "Local":
        source_path = source.removeprefix("local://")
        if not re.fullmatch(r"local://public/images/(?:generated/blog|fallback/[^/]+)/[^\s]+", source) or any(part in {".", "..", ""} for part in source_path.split("/")):
            errors.append("Local fallback requires exact local:// repository source")
    elif provider == "LocalEditorial":
        slug = str(post.get("slug") or post.get("id") or "").strip()
        if not slug or not re.fullmatch(rf"local-editorial://{re.escape(slug)}/[0-7]", source):
            errors.append("LocalEditorial fallback requires an article-bound local-editorial:// source")
    elif not re.fullmatch(r"https://[^\s/]+/\S+", source):
        errors.append("External provider image requires an exact HTTPS source URL")
    if provider == "Pexels":
        if post.get("imageCredit") != "צילום דרך Pexels":
            errors.append("Pexels image requires visible Pexels credit metadata")
        if post.get("imageCreditUrl") != source:
            errors.append("Pexels image credit URL must match the recorded source URL")
    expected_sha = proof["Image SHA-256"] or ""
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        errors.append("Committed image requires a lowercase SHA-256")
    if len(proof["Image Visual Match"] or "") < 24:
        errors.append("Committed image requires a concrete Image Visual Match sentence")
    if not re.fullmatch(r"\d+x\d+", proof["Image Dimensions"] or ""):
        errors.append("Committed image requires Image Dimensions")
    if not post.get("id") or proof["Image Article ID"] != str(post["id"]):
        errors.append("Image Article ID must match the current article")
    if proof["Image Article SHA-256"] != article_sha256(post):
        errors.append("Image Article SHA-256 must match the current article content")
    if require_head and (not re.fullmatch(r"[a-f0-9]{40}", head_sha or "") or proof["Image Evidence Head"] != head_sha):
        errors.append("Image Evidence Head must match the current PR head")
    if data is not None:
        actual_sha = hashlib.sha256(data).hexdigest()
        if actual_sha != expected_sha:
            errors.append(f"Image SHA-256 mismatch: expected {expected_sha}, got {actual_sha}")
        try:
            width, height = image_dimensions(data)
            if width < 640 or height < 360:
                errors.append(f"Image dimensions too small: {width}x{height}")
            elif not 1.2 <= width / height <= 2.2:
                errors.append(f"Image aspect ratio unsuitable for article hero: {width}x{height}")
            if proof["Image Dimensions"] != f"{width}x{height}":
                errors.append(f"Image dimensions mismatch: expected {width}x{height}")
        except ValueError as exc:
            errors.append(f"Image validation failed: {exc}")
    return errors


def replace_image_evidence(body: str, evidence: dict[str, str]) -> str:
    labels = IMAGE_EVIDENCE_FIELDS + ("Image Generation Attempt", "Image Fallback Attempt", "Image Fallback Result")
    kept = [line for line in (body or "").splitlines()
            if line.strip() != "### Image evidence (trusted automation)"
            and not any(re.match(rf"^\s*(?:[-*]\s*)?{re.escape(label)}\s*:", line, re.I) for label in labels)]
    return "\n".join(kept).rstrip() + "\n\n### Image evidence (trusted automation)\n" + "\n".join(
        f"{key}: {value}" for key, value in evidence.items()) + "\n"
