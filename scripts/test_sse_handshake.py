import os
import sys
import urllib.request
import json

api_key = os.environ.get("COMPOSIO_API_KEY")
if not api_key:
    print("Error: COMPOSIO_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)
headers = {
    "Authorization": f"Bearer {api_key}",
    "Accept": "text/event-stream"
}

req = urllib.request.Request(
    "https://connect.composio.dev/mcp",
    headers=headers,
    method="GET"
)

try:
    with urllib.request.urlopen(req) as response:
        print("Response Code:", response.getcode())
        print("Response Headers:")
        print(dict(response.info()))
        print("\nResponse Stream:")
        for _ in range(5):
            line = response.readline().decode('utf-8')
            if line:
                print(line.strip())
except Exception as e:
    print("SSE Handshake Failed:", e)
