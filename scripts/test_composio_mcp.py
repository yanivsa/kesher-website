import os
import sys
import urllib.request
import json

api_key = os.environ.get("COMPOSIO_API_KEY")
if not api_key:
    print("Error: COMPOSIO_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)
headers = {
    "x-consumer-api-key": api_key,
    "Content-Type": "application/json"
}

body = {
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 1
}

# The endpoint might be https://connect.composio.dev/mcp/tools/list or just connect.composio.dev/mcp
# Let's try connected endpoints
endpoints = [
    "https://connect.composio.dev/mcp",
    "https://connect.composio.dev/mcp/tools",
    "https://connect.composio.dev/mcp/tools/list"
]

for url in endpoints:
    print(f"\nTesting URL: {url}")
    req = urllib.request.Request(
        url,
        headers=headers,
        data=json.dumps(body).encode('utf-8'),
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            print("SUCCESS!")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
            break
    except Exception as e:
        print("Failed:", e)
