import urllib.request
import json

api_key = "ck_-hh6vYTdFqm5Mt_vvIDp"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

body = {
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {},
    "id": 1
}

url = "https://connect.composio.dev/mcp"

req = urllib.request.Request(
    url,
    headers=headers,
    data=json.dumps(body).encode('utf-8'),
    method="POST"
)

try:
    with urllib.request.urlopen(req) as response:
        print("Response Code:", response.getcode())
        data = json.loads(response.read().decode('utf-8'))
        print("SUCCESS!")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
except Exception as e:
    print("Failed:", e)
