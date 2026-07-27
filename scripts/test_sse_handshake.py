import urllib.request
import json

api_key = "ck_-hh6vYTdFqm5Mt_vvIDp"
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
