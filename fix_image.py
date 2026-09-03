import json
import os
import subprocess

with open('src/data/posts.json', 'r', encoding='utf-8') as f:
    posts = json.load(f)

used_images = {p.get('image') for p in posts if 'image' in p}
all_images = os.listdir('public/images/generated/blog')

fallback = None
for img in all_images:
    if img.endswith('.jpg') or img.endswith('.png'):
        img_path = f'/images/generated/blog/{img}'
        if img_path not in used_images:
            for post in posts:
                if post['id'] == 'smart-youth-focus-tasks-organization':
                    post['image'] = img_path
                    post['imageAlt'] = 'ילד נבון מול ציוד לימודי או בסביבה לימודית'
                    break
            with open('src/data/posts.json', 'w', encoding='utf-8') as f:
                json.dump(posts, f, indent=2, ensure_ascii=False)

            res = subprocess.run(["python3", ".github/scripts/validate-article-images.py"], capture_output=True)
            if res.returncode == 0:
                fallback = img_path
                break

print(f"Fallback found: {fallback}")
