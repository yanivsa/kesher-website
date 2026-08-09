import re
body = """This PR adds a new article to the Kesher blog focusing on the emotional and organizational challenges a gifted child faces when transitioning to a new gifted program. It includes a specific hook, a 40-80 word BLUF paragraph, varied H3 question sections, and practical actionable advice, conforming to the `הנחיית הורים` category and `הכנה למסגרת מחוננים` subcategory.

### Content Details
- **Keyword/Topic**: הכנה למסגרת מחוננים (Preparation for a gifted framework)
- **Hook**: The letter from the Ministry of Education arrives, parents are proud, but the child suddenly resists going, fearing they won't fit in or won't be the smartest anymore.
- **Category**: הנחיית הורים
- **Word Count**: 992 words
- **H3 Count**: 6

### Image Details
- **Image Generation Attempt**: DeepAI
- **Image Generation Result**: success
- **Image Source URL**: https://api.deepai.org/api/text2img (Custom generated)
- **Image SHA-256**: 13673b5b26f308d3a99743ef642e67d4cbc2561e767542eaa1c61e9a18ef578d
- **Image Dimensions**: 1200x1800
- **Image Visual Match**: A warm, emotionally supportive scene of an Israeli parent and child sitting together at home, having a quiet conversation in natural daylight, reflecting the support needed during a difficult transition.
"""

def exact_field(body: str, label: str) -> str | None:
    match = re.search(rf"(?im)^{re.escape(label)}:\s*([^\r\n]+?)\s*$", body or "")
    return match.group(1).strip() if match else None

print(exact_field(body, "Image Generation Attempt"))
print(exact_field(body, "Image Generation Result"))
print(exact_field(body, "Image Source URL"))
