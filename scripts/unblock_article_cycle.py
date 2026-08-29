#!/usr/bin/env python3
"""Safe one-time recovery script for blocked article cycles.

This script inspects durable state JSON files or state dictionaries and resets
the article stage status and attempt counters to allow safe recovery retries
without blindly wiping durable history or losing backlog tracking.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def recover_state(state: dict[str, Any], target_cycle: str | None = None) -> bool:
    if not isinstance(state, dict):
        raise ValueError("Invalid state payload: expected dictionary")

    cycle = str(state.get("cycle") or "")
    if target_cycle and cycle != target_cycle:
        print(f"Skipping cycle {cycle} (target was {target_cycle})")
        return False

    status = str(state.get("status") or "")
    article = state.get("article")
    if not isinstance(article, dict):
        print(f"Cycle {cycle} has no valid article state dict")
        return False

    last_error = state.get("last_error") or article.get("last_error") or {}
    last_code = str(last_error.get("code") or "")

    print(f"Inspecting cycle {cycle}: status='{status}', last_code='{last_code}'")

    # Reset blocked or exhausted article state for cycle recovery
    changed = False
    if status == "blocked" or article.get("status") == "exhausted" or last_code == "ARTICLE_ATTEMPTS_EXHAUSTED":
        print(f"Unblocking article stage for cycle {cycle}...")
        state["status"] = "article_needed"
        article["status"] = "pending"
        article["attempt_count"] = 0
        article["attempts"] = 0
        article["next_retry_at"] = None
        article["last_error"] = None
        state["last_error"] = None

        # Keep PR or session reference if present for safe recovery
        if article.get("pr_number"):
            state["status"] = "article_pr_open"
            print(f"Preserved article PR #{article.get('pr_number')}")
        elif article.get("last_jules_session_id"):
            print(f"Preserved Jules session identity {article.get('last_jules_session_id')}")

        state.setdefault("history", []).append({
            "at": datetime.now(timezone.utc).isoformat(),
            "from": status,
            "to": state["status"],
            "reason": "manual_recovery_script_unblock",
        })
        changed = True
    else:
        print(f"Cycle {cycle} is not blocked/exhausted. No action taken.")

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely recover blocked daily article cycles in controller state")
    parser.add_argument("--state-file", type=Path, help="Path to local state JSON file to inspect and recover")
    parser.add_argument("--cycle", default="2026-08-28", help="Target cycle date (default: 2026-08-28)")
    args = parser.parse_args()

    if not args.state_file:
        print("Usage: python3 scripts/unblock_article_cycle.py --state-file <path_to_state.json> [--cycle 2026-08-28]")
        return 0

    if not args.state_file.is_file():
        print(f"Error: file {args.state_file} does not exist", file=sys.stderr)
        return 1

    try:
        content = json.loads(args.state_file.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error reading state file {args.state_file}: {exc}", file=sys.stderr)
        return 1

    if recover_state(content, args.cycle):
        args.state_file.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Successfully recovered state in {args.state_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
