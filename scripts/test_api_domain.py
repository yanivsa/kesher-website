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
    "https://api.composio.dev/v3/toolkits",
    "https://api.composio.dev/v3/connected_accounts",
    "https://api.composio.dev/v1/toolkits",
    "https://api.composio.dev/v1/connected_accounts",
    "https://api.composio.dev/api/v3/connected_accounts"
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
            print("SUCCESS! Status:", response.getcode())
            data = json.loads(response.read().decode('utf-8'))
            print(json.dumps(data, indent=2)[:500])
    except Exception as e:
        print("Failed:", e)
