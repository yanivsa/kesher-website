import urllib.request
import re

url = "https://www.youtube.com/watch?v=q4F8t5mWjfY"
req = urllib.request.Request(
    url,
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
)

try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        
    # Search for <title> tag
    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
    if title_match:
        print("HTML Title:", title_match.group(1))
    else:
        print("Title tag not found.")
        
    # Search for meta title
    meta_match = re.search(r'meta name="title" content="(.*?)"', html)
    if meta_match:
        print("Meta Title:", meta_match.group(1))
        
except Exception as e:
    print("Failed to fetch HTML:", e)
