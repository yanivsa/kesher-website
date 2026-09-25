#!/usr/bin/env python3
"""Best-effort free stock B-roll for Kesher Remotion.

This module is deliberately non-blocking. It may return zero assets for any
reason: missing credentials, provider errors, rate limits, timeouts, unsuitable
results, download failures, invalid media, or exhausted time budget.

Only providers whose free terms fit Kesher's commercial use are included:
Pexels first, Pixabay as fallback. Coverr is intentionally excluded.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/videos/search"
PIXABAY_SEARCH_URL = "https://pixabay.com/api/videos/"
CACHE_NAME = "enhancement-stock-search-cache.json"
CACHE_TTL_SECONDS = 24 * 60 * 60
MAX_DOWNLOAD_BYTES = 30 * 1024 * 1024
DEFAULT_BUDGET_SECONDS = 12.0
PEXELS_LICENSE_URL = "https://www.pexels.com/license/"
PIXABAY_LICENSE_URL = "https://pixabay.com/service/license-summary/"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _enabled() -> bool:
    value = os.environ.get("KESHER_BROLL_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off", "disabled"}


def build_stock_query(source: dict[str, Any]) -> str:
    """Map Hebrew Kesher article cues to one conservative English stock query."""
    text = " ".join(
        str(source.get(key) or "")
        for key in ("title", "excerpt", "content", "category", "subcategory", "slug")
    ).lower()

    rules = [
        (r"כסף|תקציב|כלכל|הוצאות|פנקס|score|budget|money|financial", "couple budgeting together at home"),
        (r"טלפון|מסך|וואטסאפ|הסח|phone|screen|smartphone|distraction", "couple smartphone conversation at home"),
        (r"אמון|בגיד|שקר|קנאה|trust|infidelity|jealous", "couple serious calm conversation at home"),
        (r"מחוננ|פרפקציונ|שיעורי בית|homework|gifted|perfection", "parent supporting child studying at desk"),
        (r"קשב|adhd|בוקר|ילקוט|בית ספר|morning|school|routine", "parent child morning school routine at home"),
        (r"גבול|מחנק|מרחב|boundar|space", "couple respectful conversation living room"),
        (r"רילוקיישן|מעבר|עלייה|relocation|moving", "couple moving boxes conversation at home"),
        (r"דייט|היכרות|dating", "two adults talking over coffee"),
        (r"הור|ילד|משפחה|parent|child|family", "parent child supportive conversation at home"),
        (r"זוג|נישוא|קשר|תקשורת|מריבה|couple|marriage|relationship", "couple calm conversation at home"),
    ]
    for pattern, query in rules:
        if re.search(pattern, text):
            return query
    return "warm family home conversation"


def _load_cache(state_dir: Path) -> dict[str, Any]:
    path = state_dir / CACHE_NAME
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_cache(state_dir: Path, payload: dict[str, Any]) -> None:
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        path = state_dir / CACHE_NAME
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError:
        pass


def _cache_key(provider: str, query: str, profile: str) -> str:
    raw = f"{provider}|{profile}|{query}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _orientation_matches(width: int, height: int, profile: str) -> bool:
    if width <= 0 or height <= 0:
        return False
    if profile == "short_9_16":
        return height > width
    return width > height


def _remaining(deadline: float) -> float:
    return max(0.0, deadline - time.monotonic())


def _request_timeout(deadline: float) -> tuple[float, float]:
    remaining = _remaining(deadline)
    if remaining <= 1.0:
        raise TimeoutError("B-roll time budget exhausted")
    return (min(2.0, max(0.5, remaining / 3)), min(5.0, max(1.0, remaining - 0.5)))


def _choose_pexels_file(files: list[dict[str, Any]], profile: str) -> dict[str, Any] | None:
    usable = []
    for item in files:
        if not isinstance(item, dict):
            continue
        link = str(item.get("link") or "").strip()
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        if not link or not _orientation_matches(width, height, profile):
            continue
        if item.get("file_type") not in {None, "", "video/mp4"} and not link.lower().split("?")[0].endswith(".mp4"):
            continue
        usable.append(item)
    if not usable:
        return None
    target_long_edge = 1280 if profile == "overview_16_9" else 1920
    return min(
        usable,
        key=lambda item: abs(max(int(item.get("width") or 0), int(item.get("height") or 0)) - target_long_edge),
    )


def _search_pexels(api_key: str, query: str, profile: str, deadline: float) -> list[dict[str, Any]]:
    params = {
        "query": query,
        "orientation": "portrait" if profile == "short_9_16" else "landscape",
        "size": "medium",
        "per_page": 12,
        "page": 1,
    }
    response = requests.get(
        PEXELS_SEARCH_URL,
        headers={"Authorization": api_key},
        params=params,
        timeout=_request_timeout(deadline),
    )
    response.raise_for_status()
    payload = response.json()
    results: list[dict[str, Any]] = []
    for video in payload.get("videos", []) if isinstance(payload, dict) else []:
        if not isinstance(video, dict):
            continue
        chosen = _choose_pexels_file(video.get("video_files") or [], profile)
        if not chosen:
            continue
        results.append(
            {
                "provider": "pexels",
                "id": str(video.get("id") or "unknown"),
                "download_url": str(chosen.get("link") or ""),
                "page_url": str(video.get("url") or "https://www.pexels.com/"),
                "width": int(chosen.get("width") or 0),
                "height": int(chosen.get("height") or 0),
                "license_url": PEXELS_LICENSE_URL,
                "creator": str((video.get("user") or {}).get("name") or ""),
            }
        )
    return results


def _choose_pixabay_file(videos: dict[str, Any], profile: str) -> dict[str, Any] | None:
    for quality in ("medium", "small", "large", "tiny"):
        item = videos.get(quality) if isinstance(videos, dict) else None
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        if url and _orientation_matches(width, height, profile):
            return item
    return None


def _search_pixabay(api_key: str, query: str, profile: str, deadline: float) -> list[dict[str, Any]]:
    response = requests.get(
        PIXABAY_SEARCH_URL,
        params={
            "key": api_key,
            "q": query,
            "video_type": "film",
            "safesearch": "true",
            "per_page": 20,
            "page": 1,
        },
        timeout=_request_timeout(deadline),
    )
    response.raise_for_status()
    payload = response.json()
    results: list[dict[str, Any]] = []
    for hit in payload.get("hits", []) if isinstance(payload, dict) else []:
        if not isinstance(hit, dict):
            continue
        chosen = _choose_pixabay_file(hit.get("videos") or {}, profile)
        if not chosen:
            continue
        results.append(
            {
                "provider": "pixabay",
                "id": str(hit.get("id") or "unknown"),
                "download_url": str(chosen.get("url") or ""),
                "page_url": str(hit.get("pageURL") or "https://pixabay.com/videos/"),
                "width": int(chosen.get("width") or 0),
                "height": int(chosen.get("height") or 0),
                "license_url": PIXABAY_LICENSE_URL,
                "creator": str(hit.get("user") or ""),
            }
        )
    return results


def _provider_results(
    provider: str,
    api_key: str,
    query: str,
    profile: str,
    state_dir: Path,
    deadline: float,
) -> list[dict[str, Any]]:
    cache = _load_cache(state_dir)
    key = _cache_key(provider, query, profile)
    cached = cache.get(key) if isinstance(cache, dict) else None
    now = time.time()
    if isinstance(cached, dict):
        stored_at = float(cached.get("stored_at") or 0)
        results = cached.get("results")
        if now - stored_at < CACHE_TTL_SECONDS and isinstance(results, list):
            return [dict(row) for row in results if isinstance(row, dict)]

    if provider == "pexels":
        results = _search_pexels(api_key, query, profile, deadline)
    elif provider == "pixabay":
        results = _search_pixabay(api_key, query, profile, deadline)
    else:
        return []

    cache[key] = {"stored_at": now, "results": results}
    _save_cache(state_dir, cache)
    return results


def _probe_orientation(path: Path, profile: str) -> bool:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return True
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        payload = json.loads(result.stdout or "{}") if result.returncode == 0 else {}
        streams = payload.get("streams") if isinstance(payload, dict) else None
        if not isinstance(streams, list) or not streams:
            return False
        width = int(streams[0].get("width") or 0)
        height = int(streams[0].get("height") or 0)
        return _orientation_matches(width, height, profile)
    except Exception:
        return False


def _download_result(result: dict[str, Any], state_dir: Path, profile: str, deadline: float) -> Path | None:
    url = str(result.get("download_url") or "").strip()
    provider = re.sub(r"[^a-z0-9_-]+", "-", str(result.get("provider") or "stock").lower())
    asset_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(result.get("id") or "unknown"))
    if not url:
        return None
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    target = state_dir / f"enhancement-stock-{provider}-{asset_id}-{url_hash}.mp4"
    if target.is_file() and target.stat().st_size > 0 and _probe_orientation(target, profile):
        return target

    if _remaining(deadline) <= 1.0:
        return None
    temporary = target.with_suffix(".mp4.part")
    try:
        response = requests.get(url, stream=True, timeout=_request_timeout(deadline), allow_redirects=True)
        response.raise_for_status()
        content_length = int(response.headers.get("content-length") or 0)
        if content_length > MAX_DOWNLOAD_BYTES:
            return None
        content_type = str(response.headers.get("content-type") or "").lower()
        if content_type and not content_type.startswith("video/") and "octet-stream" not in content_type:
            return None
        total = 0
        with temporary.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=512 * 1024):
                if not chunk:
                    continue
                if _remaining(deadline) <= 0.5:
                    raise TimeoutError("B-roll download exceeded time budget")
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ValueError("B-roll download exceeded size budget")
                handle.write(chunk)
        if total <= 1024:
            return None
        temporary.replace(target)
        if not _probe_orientation(target, profile):
            target.unlink(missing_ok=True)
            return None
        return target
    except Exception:
        temporary.unlink(missing_ok=True)
        return None


def _timing_slot(duration_seconds: float, profile: str, index: int) -> tuple[float, float] | None:
    duration = max(0.0, float(duration_seconds))
    safe_end = max(0.0, duration - 3.5)
    if safe_end < 2.0:
        return None
    if profile == "short_9_16":
        fractions = (0.22,)
        length = min(2.6, max(1.6, duration * 0.08))
    else:
        fractions = (0.22, 0.62)
        length = min(4.0, max(2.5, duration * 0.035))
    fraction = fractions[min(index, len(fractions) - 1)]
    start = max(0.5, safe_end * fraction)
    start = min(start, max(0.0, safe_end - length))
    end = min(safe_end, start + length)
    if end - start < 1.0:
        return None
    return round(start, 3), round(end, 3)


def resolve_free_stock_broll(
    *,
    state_dir: Path,
    source: dict[str, Any],
    source_identity: str,
    duration_seconds: float,
    profile: str,
) -> list[dict[str, Any]]:
    """Return up to 1 Short or 2 Overview B-roll clips, never raising."""
    if not _enabled():
        return []
    pexels_key = os.environ.get("PEXELS_API_KEY", "").strip()
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not pexels_key and not pixabay_key:
        return []

    max_assets = 1 if profile == "short_9_16" else 2
    try:
        configured_budget = float(os.environ.get("KESHER_BROLL_BUDGET_SECONDS", DEFAULT_BUDGET_SECONDS))
    except ValueError:
        configured_budget = DEFAULT_BUDGET_SECONDS
    budget = min(20.0, max(4.0, configured_budget))
    deadline = time.monotonic() + budget
    query = build_stock_query(source)
    providers = (("pexels", pexels_key), ("pixabay", pixabay_key))
    candidates: list[dict[str, Any]] = []

    for provider, api_key in providers:
        if not api_key or len(candidates) >= max_assets or _remaining(deadline) <= 1.0:
            continue
        try:
            results = _provider_results(provider, api_key, query, profile, state_dir, deadline)
        except Exception:
            continue
        for result in results:
            if len(candidates) >= max_assets or _remaining(deadline) <= 0.8:
                break
            try:
                path = _download_result(result, state_dir, profile, deadline)
            except Exception:
                path = None
            if not path:
                continue
            timing = _timing_slot(duration_seconds, profile, len(candidates))
            if not timing:
                break
            start, end = timing
            provider_name = str(result.get("provider") or provider)
            page_url = str(result.get("page_url") or "").strip()
            license_url = str(result.get("license_url") or "").strip()
            creator = str(result.get("creator") or "").strip()
            candidates.append(
                {
                    "asset_ref": path.name,
                    "type": "broll",
                    "source": page_url or f"{provider_name}:{result.get('id')}",
                    "provenance": f"{provider_name} API free-stock asset {result.get('id')}",
                    "provider": provider_name,
                    "provider_asset_id": str(result.get("id") or ""),
                    "provider_url": page_url,
                    "license_url": license_url,
                    "creator": creator,
                    "usage_status": "approved",
                    "semantic_fit": 0.72,
                    "sha256": _sha256(path),
                    "start": start,
                    "end": end,
                    "intent": f"brief supporting B-roll for narration cue: {query}",
                    "source_identity": source_identity,
                }
            )
    return candidates
