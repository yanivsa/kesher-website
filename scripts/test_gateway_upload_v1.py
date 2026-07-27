import urllib.request
import json

api_key = "ck_-hh6vYTdFqm5Mt_vvIDp"
headers = {
    "x-consumer-api-key": api_key,
    "Content-Type": "application/json"
}

body = {
    "name": "test.mp4",
    "mimetype": "video/mp4"
}

urls = [
    "https://connect.composio.dev/api/v1/files/upload/request",
    "https://connect.composio.dev/api/v1/files/upload",
    "https://connect.composio.dev/api/v1/files",
    "https://connect.composio.dev/v1/files/upload/request"
]

for url in urls:
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
            print("SUCCESS! Status:", response.getcode())
            print(json.dumps(data, indent=2))
            break
    except Exception as e:
        print("Failed:", e)
