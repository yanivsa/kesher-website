import json
import re

with open("src/data/posts.json", "r", encoding="utf-8") as f:
    posts = json.load(f)

for post in posts:
    if post["id"] == "child-does-not-want-kindergarten":
        # The user said:
        # The exact head ad27a8b08d65d50624bb20301348b3116cb22f50 still contains ungrammatical opening `ואתם עומדים מול ילד לא רוצה ללכת לגן`
        # We need to rewrite naturally in Hebrew while preserving the primary search phrase elsewhere.

        # Primary keyword: ילד לא רוצה ללכת לגן
        # We can place it elsewhere naturally. e.g.
        # "אם יש לכם ילד לא רוצה ללכת לגן ומתנגד מדי בוקר..."
        # or "לפעמים נראה שכל בוקר הופך למאבק כי ילד לא רוצה ללכת לגן..."
        # Oh, let's fix it by rewriting that sentence.

        old_content = post["content"]
        new_content = old_content.replace(
            "ואתם עומדים מול ילד לא רוצה ללכת לגן שמסרב בכל תוקף להתארגן.",
            "ואתם מוצאים את עצמכם שוב ושוב באותו מצב מתסכל: ילד לא רוצה ללכת לגן ומסרב בכל תוקף להתארגן."
        )
        post["content"] = new_content
        print(new_content)

with open("src/data/posts.json", "w", encoding="utf-8") as f:
    json.dump(posts, f, ensure_ascii=False, indent=2)
    f.write('\n')
