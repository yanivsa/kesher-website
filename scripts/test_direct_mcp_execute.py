import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    
    # Run the tool YOUTUBE_UPLOAD_VIDEO via COMPOSIO_MULTI_EXECUTE_TOOL
    # We pass the public URL of the video as the s3key!
    result = client.call_tool("COMPOSIO_MULTI_EXECUTE_TOOL", {
        "sync_response_to_workbench": False,
        "current_step": "UPLOADING_VIDEO",
        "memory": {},
        "tools": [
            {
                "tool_slug": "YOUTUBE_UPLOAD_VIDEO",
                "arguments": {
                    "title": "למה בעלך לא משתף אותך? (בדיקה)",
                    "description": "סרטון בדיקה קצר לערוץ קשר",
                    "tags": ["בדיקה"],
                    "categoryId": "22",
                    "privacyStatus": "private",  # keep it private for test!
                    "videoFilePath": {
                        "name": "test_video.mp4",
                        "mimetype": "video/mp4",
                        "s3key": "https://tmpfiles.org/dl/w1wRaA5KKTFH/test_video.mp4"
                    }
                }
            }
        ]
    })
    print("Multi Execute Result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
finally:
    client.disconnect()
