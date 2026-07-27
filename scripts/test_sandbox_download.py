import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    # Execute remote bash to download the video to /tmp
    result = client.call_tool("COMPOSIO_REMOTE_BASH_TOOL", {
        "command": "wget -O /tmp/test_video.mp4 https://tmpfiles.org/dl/w1wRaA5KKTFH/test_video.mp4 && ls -la /tmp/test_video.mp4"
    })
    print("Remote Download Result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
finally:
    client.disconnect()
