import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    # Call YOUTUBE_GET_VIDEO_DETAILS_BATCH with connected_account_id
    result = client.call_tool("COMPOSIO_MULTI_EXECUTE_TOOL", {
        "sync_response_to_workbench": False,
        "current_step": "CHECKING_PROCESSING",
        "memory": {},
        "tools": [
            {
                "tool_slug": "YOUTUBE_GET_VIDEO_DETAILS_BATCH",
                "connected_account_id": "youtube_ransom-winish",
                "arguments": {
                    "id": ["LRx4H04hnMA"],
                    "parts": ["snippet", "status", "processingDetails"]
                }
            }
        ]
    })
    print("Video Processing Details:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
finally:
    client.disconnect()
