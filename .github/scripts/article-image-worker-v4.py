#!/usr/bin/env python3
"""Trusted article image worker with a deterministic local terminal fallback.

External providers are optional enhancements. The terminal local provider reads
only versioned assets from the trusted ``main`` checkout and validates the real
bytes before use. Each semantic category has at least one repository-curated
landscape candidate, and runtime falls through candidates if one is missing or
invalid.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

V3_PATH = Path(__file__).with_name("article-image-worker-v3.py")
spec = importlib.util.spec_from_file_location("kesher_article_image_worker_v3", V3_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load image worker v3 from {V3_PATH}")
v3 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v3
spec.loader.exec_module(v3)

core = v3.core
REPO_ROOT = Path(__file__).resolve().parents[2]

try_gemini = v3.try_gemini
try_unsplash = v3.try_unsplash
try_pexels = v3.try_pexels
summaries = v3.summaries
trusted_image_present = v3.trusted_image_present
commit_files = v3.commit_files

# All primary assets below have real encoded dimensions inside the hero-image
# acceptance range. Runtime still validates every byte before use.
LOCAL_FALLBACK_CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "dating": [
        ("public/images/generated/blog/dating-communication-early-stages.jpg", "שני אנשים בשיחה רגועה בשלב היכרות זוגית"),
    ],
    "singles": [
        ("public/images/generated/blog/late-singleness-friends-moving-forward.jpg", "אדם בסיטואציה חברתית המתאימה לנושא רווקות וקשרים"),
        ("public/images/generated/blog/dating-communication-early-stages.jpg", "שני אנשים בשיחה רגועה סביב היכרות וקשר"),
    ],
    "relocation": [
        ("public/images/generated/blog/relocation-career-loss-and-dependence.jpg", "זוג בסיטואציה ביתית הקשורה לשינויי חיים ורילוקיישן"),
        ("public/images/generated/blog/dating-communication-early-stages.jpg", "זוג בשיחה פנים אל פנים על שינוי בחיים המשותפים"),
    ],
    "premarital": [
        ("public/images/generated/blog/dating-communication-early-stages.jpg", "זוג בשיחה רגועה לקראת בניית חיים משותפים"),
    ],
    "parenting": [
        ("public/images/generated/blog/child-after-school-restraint-collapse.jpg", "ילד בבית לאחר יום לימודים לצד נוכחות הורית תומכת"),
    ],
    "gifted": [
        ("public/images/generated/blog/child-after-school-restraint-collapse.jpg", "ילד לאחר מסגרת לימודית ברגע רגשי הדורש תמיכה והכלה"),
    ],
    "adhd": [
        ("public/images/generated/blog/adhd-and-screen-addiction-strategies.jpg", "ילד בסביבה ביתית המתאימה להדרכת הורים סביב קשב וויסות"),
        ("public/images/generated/blog/child-after-school-restraint-collapse.jpg", "ילד בבית לאחר יום לימודים לצד נוכחות הורית תומכת"),
    ],
    "couples": [
        ("public/images/generated/blog/dating-communication-early-stages.jpg", "זוג בשיחה פנים אל פנים המדגישה תקשורת וקשר"),
    ],
}


def provider_preflight() -> dict[str, bool]:
    availability = {
        "gemini": bool((os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()),
        "unsplash": bool((os.environ.get("UNSPLASH_ACCESS_KEY") or "").strip()),
        "pexels": bool((os.environ.get("PEXELS_API_KEY") or "").strip()),
        "local": True,
    }
    print(
        "IMAGE_PROVIDER_PREFLIGHT "
        + " ".join(f"{name}={'configured' if ready else 'missing'}" for name, ready in availability.items()),
        file=sys.stderr,
        flush=True,
    )
    return availability


def _trusted_candidate_path(source_path: str) -> Path:
    candidate_path = (REPO_ROOT / source_path).resolve()
    trusted_root = REPO_ROOT.resolve()
    if trusted_root != candidate_path and trusted_root not in candidate_path.parents:
        raise RuntimeError("Refusing local fallback path outside trusted checkout")
    return candidate_path


def local_fallback(
    repo: str,
    post: dict[str, Any],
    _head_ref: str,
    _token: str,
    attempts: list[str],
) -> core.ImageCandidate:
    """Return the first valid curated landscape image from trusted main bytes."""
    attempts.append("local-curated")
    category = core.article_key(post)
    candidates = LOCAL_FALLBACK_CANDIDATES.get(category) or LOCAL_FALLBACK_CANDIDATES["couples"]
    failures: list[str] = []
    for source_path, description in candidates:
        try:
            candidate_path = _trusted_candidate_path(source_path)
            if not candidate_path.is_file():
                raise RuntimeError("missing")
            data = candidate_path.read_bytes()
            width, height, ext = core.validate_candidate(data)
            print(
                f"IMAGE_LOCAL_FALLBACK_READY category={category} path={source_path} dimensions={width}x{height}",
                file=sys.stderr,
                flush=True,
            )
            return core.ImageCandidate(
                "Local",
                data,
                ext,
                f"local://{source_path}",
                description,
                attempts.copy(),
            )
        except Exception as exc:
            failures.append(f"{source_path}:{type(exc).__name__}")
            print(
                f"IMAGE_LOCAL_FALLBACK_REJECTED category={category} path={source_path} error={type(exc).__name__}",
                file=sys.stderr,
                flush=True,
            )
    raise RuntimeError(
        "No valid trusted local fallback remained for " + category + ": " + ", ".join(failures)
    )


def choose_candidate(repo: str, post: dict[str, Any], head_ref: str, token: str) -> core.ImageCandidate:
    attempts: list[str] = []
    for provider in (try_gemini, try_unsplash, try_pexels):
        candidate = provider(post, attempts)
        if candidate:
            return candidate
    return local_fallback(repo, post, head_ref, token, attempts)


v3.local_fallback = local_fallback
v3.choose_candidate = choose_candidate
ensure_image = v3.ensure_image


def main() -> int:
    provider_preflight()
    return v3.main()


if __name__ == "__main__":
    raise SystemExit(main())
