import os
import sys
import urllib.request
import json

api_key = os.environ.get("COMPOSIO_API_KEY")
if not api_key:
    print("Error: COMPOSIO_API_KEY environment variable is not set.", file=sys.stderr)
    sys.exit(1)

# Try different configurations
configs = [
    {
        "url": "https://backend.composio.dev/api/v3/connected_accounts",
        "headers": {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
    },
    {
        "url": "https://backend.composio.dev/api/v3/connected_accounts",
        "headers": {
            "x-consumer-api-key": api_key,
            "Content-Type": "application/json"
        }
    },
    {
        "url": "https://backend.composio.dev/api/v3/connections",
        "headers": {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
    }
]

for idx, config in enumerate(configs, 1):
    print(f"\n--- Testing Config {idx} ---")
    print(f"URL: {config['url']}")
    print(f"Headers: {list(config['headers'].keys())}")
    req = urllib.request.Request(
        config["url"],
        headers=config["headers"],
        method="GET"
    )
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            print("SUCCESS!")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
            break
    except Exception as e:
        print("Failed:", e)
