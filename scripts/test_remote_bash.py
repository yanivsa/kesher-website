import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    # Execute remote bash to check Composio methods
    result = client.call_tool("COMPOSIO_REMOTE_BASH_TOOL", {
        "command": "python3 -c 'from composio import Composio; print(dir(Composio))'"
    })
    print("Remote Composio Methods:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
finally:
    client.disconnect()
