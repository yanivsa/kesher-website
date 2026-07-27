import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    # Python script content to print lines of _client.py
    py_script = """
with open("/usr/local/lib/python3.13/site-packages/composio_client/_client.py", "r") as f:
    lines = f.readlines()
print("=== lines 170-190 ===")
for i in range(169, min(190, len(lines))):
    print(f"{i+1}: {lines[i]}", end="")
print("=== lines 380-410 ===")
for i in range(379, min(410, len(lines))):
    print(f"{i+1}: {lines[i]}", end="")
""".replace('"', '\\"')

    # Run command in sandbox
    result = client.call_tool("COMPOSIO_REMOTE_BASH_TOOL", {
        "command": f'python3 -c "{py_script}"'
    })
    print("Remote _client.py Content:")
    if result and "content" in result:
        print(json.loads(result["content"][0]["text"])["data"]["stdout"])
finally:
    client.disconnect()
