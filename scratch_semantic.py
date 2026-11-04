import json

with open("src/data/posts.json", "r", encoding="utf-8") as f:
    posts = json.load(f)

# Semantic keyword check fails for "ילד לא רוצה ללכת לגן"
# Can we change the primary keyword in PR body?
# Wait, "Slug 'child-does-not-want-kindergarten' could not be semantically verified: unknown keyword 'ילד לא רוצה ללכת לגן' has no trusted semantic mapping"
# And we must use this slug and keyword, but we can provide Trusted Stems in the PR body.
# Did it pick up our Trusted Semantic Stems?
# Let's check validate-article-pr.py to see how it extracts them.
