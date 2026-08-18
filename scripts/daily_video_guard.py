#!/usr/bin/env python3
"""Report whether today's scheduled Kesher video has already been uploaded."""

from __future__ import annotations

from datetime import date
from typing import Any

try:
    from kesher_daily_pipeline import israel_now, load_state
except ImportError:
    from scripts.kesher_daily_pipeline import israel_now, load_state


def already_uploaded_today(state: dict[str, Any], today: date) -> bool:
    israel_date = today.isoformat()
    return any(
        item.get("israel_date") == israel_date
        and (item.get("uploaded") is True or item.get("status") == "uploaded")
        for item in state.get("items", [])
    )


def main() -> int:
    print("true" if already_uploaded_today(load_state(), israel_now().date()) else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
