import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    # Call YOUTUBE_LIST_CHANNEL_VIDEOS via COMPOSIO_MULTI_EXECUTE_TOOL
    result = client.call_tool("COMPOSIO_MULTI_EXECUTE_TOOL", {
        "sync_response_to_workbench": False,
        "current_step": "LISTING_VIDEOS",
        "memory": {},
        "tools": [
            {
                "tool_slug": "YOUTUBE_LIST_CHANNEL_VIDEOS",
                "connected_account_id": "youtube_ransom-winish",
                "arguments": {
                    "mine": True,
                    "maxResults": 10
                }
            }
        ]
    })
    print("User Videos:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
finally:
    client.disconnect()
