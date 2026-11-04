import json
import re

with open("src/data/posts.json", "r", encoding="utf-8") as f:
    posts = json.load(f)

for post in posts:
    if post["id"] == "child-does-not-want-kindergarten":
        # Check links
        content = post["content"]
        links = re.findall(r'href=["\'](.*?)["\']', content)
        print("Existing links:", links)
