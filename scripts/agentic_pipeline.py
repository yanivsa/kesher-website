#!/usr/bin/env python3
import os
import sys
import logging
import asyncio
from datetime import datetime
from pathlib import Path

from google.antigravity import Agent, LocalAgentConfig, types
from google.antigravity.triggers import every, TriggerContext

# Configuration constants
NOTEBOOK_ID = "e101e7d7-5305-45b3-a611-21a5475ceb63"
YOUTUBE_CHANNEL_ID = "UCx5fEFvdVf28HLAR2dFW64Q"
COMPOSIO_CONNECTED_ACCOUNT = "youtube_ransom-winish"
SITE_URL = "https://kesher.saharoni.com"

import agentic_pipeline_tools as apt

# Config for Subagents
capabilities = types.CapabilitiesConfig(
    enable_subagents=True,
    enable_bash=True,
)

mcp_servers = [
    # Composio MCP Server
    types.McpStdioServer(
        command="npx",
        args=["-y", "@composio/mcp"],
    ),
    # NotebookLM MCP Server
    types.McpStdioServer(
        command="npx",
        args=["-y", "@roomi-fields/notebooklm-mcp"],
    )
]

def search_youtube_candidates(query: str, max_results: int = 5) -> str:
    """Searches YouTube for video ideas and returns a JSON string of candidates.
    
    Args:
        query: The search query in Hebrew (e.g., 'טיפים לזוגיות')
        max_results: Max number of candidates.
    """
    import json
    return json.dumps(apt.search_youtube_candidates(query, max_results), ensure_ascii=False)

def run_remotion_render(input_mp4: str, output_mp4: str, metadata_json: str, format_type: str) -> str:
    """Runs Remotion to render the final cinematic video.
    
    Args:
        input_mp4: Path to the raw video downloaded from NotebookLM.
        output_mp4: Destination path for the upgraded video.
        metadata_json: JSON string with title, description, contentTheme, beatLabels.
        format_type: 'short' or 'normal'.
    """
    import json
    try:
        metadata = json.loads(metadata_json)
    except Exception as e:
        return f"Failed to parse metadata: {e}"
    success, msg = apt.run_remotion_render(Path(input_mp4), Path(output_mp4), metadata, format_type)
    return "Success" if success else f"Error: {msg}"

def create_visual_contact_sheet(video_path: str, format_type: str) -> str:
    """Creates a 4-frame contact sheet from the video for visual QA.
    
    Args:
        video_path: Path to the MP4 file.
        format_type: 'short' or 'normal'.
    """
    path, msg = apt.create_visual_contact_sheet(Path(video_path), format_type)
    if path:
        return f"Contact sheet created at: {path}"
    return f"Error: {msg}"

def run_youtube_upload_tunnel(video_path: str, title: str, description: str, tags: list) -> str:
    """Uploads the video to YouTube using a localtunnel and Composio Workbench.
    This function handles the complex S3/Composio upload automatically.
    
    Args:
        video_path: Path to the final MP4.
        title: YouTube title.
        description: YouTube description.
        tags: List of tags.
    """
    success, yt_id, msg = apt.verify_channel_and_upload(Path(video_path), title, description, tags, is_test=False)
    if success:
        return f"Success! Video uploaded at: {msg}"
    return f"Upload failed: {yt_id} {msg}"

config = LocalAgentConfig(
    system_instructions="""
אתה סוכן ראשי האחראי על תזמון וייצור הצינור היומי של סרטוני Kesher.
עליך לנהל את סוכני המשנה להפקת, בדיקת והעלאת סרטון אחד ביום.

ארכיטקטורת הסוכנים שאתה מנהל (צור אותם במידת הצורך):
1. 'Content Creator Subagent': ימצא נושא, ישתמש ב-NotebookLM MCP לייצור וידאו ויפעיל Remotion.
2. 'Visual QA Subagent': יקבל וידאו, יריץ ffmpeg ליצירת Contact Sheet 4 פריימים ויאשר חזותית שאין טקסט באנגלית (מלבד URL), שאין שקופיות ושאין פגמים.
3. 'Publisher Subagent': יאמת מול Composio את הערוץ ויעלה את הווידאו שאושר ליוטיוב.

פעל ברקע ודאג לרישום אירועים מסודר ליומן.
""",
    capabilities=capabilities,
    mcp_servers=mcp_servers,
    tools=[search_youtube_candidates, run_remotion_render, create_visual_contact_sheet, run_youtube_upload_tunnel]
)

async def trigger_daily_pipeline(ctx: TriggerContext):
    logging.info(f"[{datetime.now()}] מפעיל פייפליין יומי...")
    await ctx.send("התחל את הליך ייצור הסרטון היומי. יצר או הפעל את סוכן היצירה, לאחר מכן בקרת איכות ולבסוף העלאה. ודא תקינות מלאה מול YouTube Channel ID: UCx5fEFvdVf28HLAR2dFW64Q.")

def main():
    logging.basicConfig(level=logging.INFO)
    
    # Run every 24 hours (86400 seconds).
    daily_trigger = every(86400, trigger_daily_pipeline)
    config.triggers = [daily_trigger]
    
    async def run_agent():
        async with Agent(config) as agent:
            logging.info("Agentic Pipeline is running. Waiting for triggers...")
            
            # Initial run for testing immediately on startup
            if "--test-mode" in sys.argv:
                logging.info("Test mode activated. Triggering immediate run.")
                response = await agent.chat("הרץ טסט של יצירת וידאו כעת דרך סוכני המשנה שלך מבלי להעלות אותו בפועל.")
                print(await response.text())
            
            # Keep alive
            while True:
                await asyncio.sleep(3600)
                
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        logging.info("Shutting down pipeline.")

if __name__ == "__main__":
    main()
