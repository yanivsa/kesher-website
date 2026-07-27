#!/usr/bin/env python3
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.append("scripts")
from notebooklm_client import NotebookLMClient


NOTEBOOK_ID = "e101e7d7-5305-45b3-a611-21a5475ceb63"
NOTEBOOK_URL = f"https://notebooklm.google.com/notebook/{NOTEBOOK_ID}?hl=en"

CANDIDATES = [
    {
        "url": "https://www.youtube.com/watch?v=QVzjpD48iuA",
        "topic": "הורות עדינה, ויסות רגשי וגבולות בבית",
    },
    {
        "url": "https://www.youtube.com/watch?v=ScaveTQhsb0",
        "topic": "חוסן רגשי אצל ילדים ותגובה הורית רגועה",
    },
    {
        "url": "https://www.youtube.com/watch?v=OmhvFzqX_Ic",
        "topic": "גבולות עם ילדים בלי לאבד חיבור רגשי",
    },
    {
        "url": "https://www.youtube.com/watch?v=KnSc1dJwcs0",
        "topic": "שתיקה, ריבים ותקשורת זוגית",
    },
    {
        "url": "https://www.youtube.com/watch?v=AL5jkox11sg",
        "topic": "טעות הורית נפוצה, אחריות וגבולות",
    },
]


def main():
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path("/Users/ninja/Documents/Kesher/notebooklm-output")
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"kesher-daily-notebooklm-{stamp}.mp4"
    log_path = out_dir / f"kesher-daily-notebooklm-{stamp}.json"

    log = {
        "started_at": datetime.now().isoformat(),
        "notebook_url": NOTEBOOK_URL,
        "candidates": CANDIDATES,
        "attempts": [],
        "output_path": str(output_path),
    }

    prompt = """
הפוך את התמה של המקור שנוסף עכשיו לסרטון YouTube מלא בעברית עבור הערוץ "קשר - ייעוץ זוגי ומשפחתי".

דרישות:
- ליצור Video Overview faceless בעברית.
- לא להעתיק שמות, דמויות, מבנה או ניסוחים מהמקור.
- להשתמש בשמות עבריים חדשים בלבד.
- ליצור גרסה אלטרנטיבית מאותה תמה אבל מזווית אחרת, מקרה אחר, מבנה אחר ודמויות אחרות.
- התוכן צריך להיות ויראלי, רגשי, ברור, מקצועי ומתאים לייעוץ זוגי/הנחיית הורים.
- לשמור על טון מכבד ולא אבחוני מדי.
"""

    client = NotebookLMClient()
    try:
        client.connect()

        selected = None
        for candidate in CANDIDATES:
            attempt = {
                "url": candidate["url"],
                "topic": candidate["topic"],
                "started_at": datetime.now().isoformat(),
            }
            print(f"Adding source: {candidate['url']}")
            try:
                result = client.call_tool(
                    "source_add",
                    {
                        "source_type": "youtube",
                        "url": candidate["url"],
                        "notebook_url": NOTEBOOK_URL,
                    },
                )
                attempt["source_add"] = result
                raw = json.dumps(result, ensure_ascii=False)
                if "success" in raw.lower() or "source" in raw.lower() or "title" in raw.lower():
                    selected = candidate
                    print(f"Selected source: {candidate['url']}")
                    break
            except Exception as exc:
                attempt["error"] = str(exc)
                print(f"Source failed: {exc}")
            finally:
                log["attempts"].append(attempt)
                log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

        if not selected:
            raise RuntimeError("No YouTube source was added successfully to NotebookLM.")

        time.sleep(20)
        print("Generating Video Overview...")
        gen_result = client.call_tool(
            "content_generate",
            {
                "content_type": "video",
                "video_style": "cinematic",
                "custom_instructions": prompt,
                "language": "Hebrew",
                "notebook_url": NOTEBOOK_URL,
            },
            timeout=900,
        )
        log["selected_source"] = selected
        log["content_generate"] = gen_result
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

        time.sleep(20)
        print(f"Downloading Video Overview to {output_path}...")
        try:
            download_result = client.call_tool(
                "content_download",
                {
                    "content_type": "video",
                    "output_path": str(output_path),
                    "notebook_url": NOTEBOOK_URL,
                },
                timeout=600,
            )
        except Exception as exc:
            download_result = {"success": False, "error": str(exc)}

        log["content_download"] = download_result
        log["finished_at"] = datetime.now().isoformat()
        if output_path.exists():
            log["downloaded_size"] = output_path.stat().st_size
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

        print(json.dumps(log, ensure_ascii=False, indent=2))
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"NotebookLM download failed; log saved to {log_path}")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
