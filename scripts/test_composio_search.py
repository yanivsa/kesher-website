import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    # Search for youtube tools
    result = client.call_tool("COMPOSIO_SEARCH_TOOLS", {
        "query": "youtube"
    })
    print("Search Result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
finally:
    client.disconnect()
