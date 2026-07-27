import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    
    code = """
res, err = run_composio_tool("YOUTUBE_GET_VIDEO_DETAILS_BATCH", {
    "id": ["LRx4H04hnMA"],
    "parts": ["status", "snippet"]
})
if err:
    print("Error fetching details:", err)
else:
    print("Details response:")
    print(res)
"""

    print("Executing check in remote workbench...")
    result = client.call_tool("COMPOSIO_REMOTE_WORKBENCH", {
        "code_to_execute": code,
        "sync_response_to_workbench": False
    })
    
    print("\n--- Workbench Output ---")
    if result and "content" in result:
        text_content = result["content"][0].get("text", "")
        try:
            parsed = json.loads(text_content)
            print("STDOUT:")
            print(parsed.get("data", {}).get("stdout", ""))
            print("STDERR:")
            print(parsed.get("data", {}).get("stderr", ""))
        except Exception:
            print(text_content)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))

finally:
    client.disconnect()
