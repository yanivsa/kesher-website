import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

client = ComposioMCPClient()
try:
    client.connect()
    # Python script content to patch _client.py
    py_script = """
file_path = "/usr/local/lib/python3.13/site-packages/composio_client/_client.py"
with open(file_path, "r") as f:
    content = f.read()

target = '        return {"x-api-key": api_key}'
replacement = '''        if api_key.startswith("ck_"):
            return {"x-consumer-api-key": api_key}
        return {"x-api-key": api_key}'''

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, "w") as f:
        f.write(content)
    print("PATCH SUCCESSFUL!")
else:
    print("Target not found in file.")
""".replace('"', '\\"')

    # Run command in sandbox
    result = client.call_tool("COMPOSIO_REMOTE_BASH_TOOL", {
        "command": f'python3 -c "{py_script}"'
    })
    print("Sandbox Patch Result:")
    if result and "content" in result:
        print(json.loads(result["content"][0]["text"])["data"]["stdout"])
finally:
    client.disconnect()
