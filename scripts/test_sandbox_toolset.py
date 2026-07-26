import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    # Python script content
    py_script = """
import os
from composio import Composio
c = Composio()
print("Composio API key when initialized empty:", c.api_key)
""".replace('"', '\\"')

    # Run command in sandbox
    result = client.call_tool("COMPOSIO_REMOTE_BASH_TOOL", {
        "command": f'python3 -c "{py_script}"'
    })
    print("Sandbox default initialization:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
finally:
    client.disconnect()
