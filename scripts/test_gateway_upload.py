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

urls = [
    "https://connect.composio.dev/api/v1/connected_accounts",
    "https://connect.composio.dev/api/connected_accounts",
    "https://connect.composio.dev/connected_accounts",
    "https://connect.composio.dev/mcp/connected_accounts"
]

for url in urls:
    print(f"\nTesting URL: {url}")
    req = urllib.request.Request(
        url,
        headers=headers,
        method="GET"
    )
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            print("SUCCESS! Status:", response.getcode())
            print(json.dumps(data, indent=2)[:500])
            break
    except Exception as e:
        print("Failed:", e)
