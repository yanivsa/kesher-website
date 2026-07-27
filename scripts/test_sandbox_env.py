import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    # Execute remote bash to print all env variables
    result = client.call_tool("COMPOSIO_REMOTE_BASH_TOOL", {
        "command": "env"
    })
    print("Remote Sandbox Env:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
finally:
    client.disconnect()
