import urllib.request
import json

api_key = "ck_-hh6vYTdFqm5Mt_vvIDp"
headers = {
    "x-consumer-api-key": api_key,
    "Content-Type": "application/json"
}

endpoints = [
    "https://backend.composio.dev/api/v3/toolkits",
    "https://backend.composio.dev/api/v3/connected_accounts"
]

for url in endpoints:
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
