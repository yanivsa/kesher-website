import urllib.request
import json

api_key = "ck_-hh6vYTdFqm5Mt_vvIDp"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

body = {
    "name": "test_video.mp4",
    "mimetype": "video/mp4"
}

urls = [
    "https://backend.composio.dev/api/v3/files/upload/request",
    "https://backend.composio.dev/api/v3.1/files/upload/request",
    "https://backend.composio.dev/api/v3/files/upload",
    "https://backend.composio.dev/api/v3/files"
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
            print("SUCCESS!")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            break
    except Exception as e:
        print("Failed:", e)
