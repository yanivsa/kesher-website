#!/usr/bin/env python3
"""Best-effort trusted image worker for Kesher Pipeline v3.

This adapter keeps the hardened v3 provider chain but fixes the guaranteed local
fallback to read from the trusted `main` checkout already present on the runner.
It also reports provider availability without exposing secret values.
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

# Re-export the hardened provider/validation helpers so tests and callers retain
# the same patchable surface as v3.
try_gemini = v3.try_gemini
try_unsplash = v3.try_unsplash
try_pexels = v3.try_pexels
summaries = v3.summaries
trusted_image_present = v3.trusted_image_present
commit_files = v3.commit_files


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


def local_fallback(
    repo: str,
    post: dict[str, Any],
    _head_ref: str,
    _token: str,
    attempts: list[str],
) -> core.ImageCandidate:
    """Read the curated fallback from the trusted checkout, never via PR/API bytes."""
    attempts.append("local-curated")
    source_path, description = core.LOCAL_FALLBACKS[core.article_key(post)]
    candidate_path = (REPO_ROOT / source_path).resolve()
    trusted_root = REPO_ROOT.resolve()
    if trusted_root != candidate_path and trusted_root not in candidate_path.parents:
        raise RuntimeError("Refusing local fallback path outside trusted checkout")
    if not candidate_path.is_file():
        raise RuntimeError(f"Trusted local fallback is missing: {source_path}")
    data = candidate_path.read_bytes()
    _width, _height, ext = core.validate_candidate(data)
    return core.ImageCandidate(
        "Local",
        data,
        ext,
        f"local://{source_path}",
        description,
        attempts.copy(),
    )


def choose_candidate(repo: str, post: dict[str, Any], head_ref: str, token: str) -> core.ImageCandidate:
    attempts: list[str] = []
    for provider in (try_gemini, try_unsplash, try_pexels):
        candidate = provider(post, attempts)
        if candidate:
            return candidate
    return local_fallback(repo, post, head_ref, token, attempts)


# v3.ensure_image resolves choose_candidate from its module globals at runtime.
# Patch only that dependency; keep the rest of the hardened atomic/idempotent
# implementation unchanged.
v3.local_fallback = local_fallback
v3.choose_candidate = choose_candidate
ensure_image = v3.ensure_image


def main() -> int:
    provider_preflight()
    return v3.main()


if __name__ == "__main__":
    raise SystemExit(main())
