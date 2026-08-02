import re
from pathlib import Path

content = Path("scripts/kesher_daily_pipeline.py").read_text(encoding="utf-8")

functions_to_extract = [
    "search_youtube_candidates",
    "remotion_content_plan",
    "media_metadata",
    "run_remotion_render",
    "create_visual_contact_sheet",
    "find_free_port",
    "serve_video_through_localtunnel",
    "verify_channel_and_upload",
    "get_youtube_video_record",
    "find_video_record",
    "decode_mcp_payloads",
    "iter_nested_values",
    "verify_public_youtube_video",
    "extract_uploaded_video_candidates",
    "validate_hebrew_metadata"
]

out = [
    "import os",
    "import re",
    "import json",
    "import time",
    "import shutil",
    "import subprocess",
    "import urllib.request",
    "import urllib.parse",
    "import contextlib",
    "import select",
    "import socket",
    "import requests",
    "from pathlib import Path",
    "from datetime import datetime",
    "",
    "PROJECT_DIR = Path('/Users/ninja/Documents/Kesher')",
    "REMOTION_DIR = PROJECT_DIR / 'remotion-kesher'",
    "SITE_URL = 'https://kesher.saharoni.com'",
    "YOUTUBE_CHANNEL_ID = 'UCx5fEFvdVf28HLAR2dFW64Q'",
    "COMPOSIO_CONNECTED_ACCOUNT = 'youtube_ransom-winish'",
    ""
]

for func in functions_to_extract:
    # Regex to capture a top-level function definition
    pattern = r"^(def\s+" + func + r"\b.*?)(?=\n^def\s|\n^@|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if match:
        out.append(match.group(1))
        out.append("\n")

Path("scripts/agentic_pipeline_tools.py").write_text("\n".join(out), encoding="utf-8")
print("Extraction complete.")
