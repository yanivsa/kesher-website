import base64
import sys
sys.path.append('scripts')
from composio_mcp_client import ComposioMCPClient
import json

# Read local script
with open("scripts/sandbox_upload.py", "rb") as f:
    script_bytes = f.read()

base64_str = base64.b64encode(script_bytes).decode('utf-8')

client = ComposioMCPClient()
try:
    client.connect()
    # Write and run the script in the remote sandbox
    print("Sending script to remote sandbox and executing upload flow...")
    result = client.call_tool("COMPOSIO_REMOTE_BASH_TOOL", {
        "command": f"echo '{base64_str}' | base64 -d > /tmp/upload.py && python3 /tmp/upload.py"
    })
    print("\n--- Sandbox Output ---")
    if result and "content" in result:
        text_content = result["content"][0].get("text", "")
        try:
            parsed = json.loads(text_content)
            print(parsed.get("data", {}).get("stdout", ""))
            print(parsed.get("data", {}).get("stderr", ""))
        except Exception:
            print(text_content)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
finally:
    client.disconnect()
