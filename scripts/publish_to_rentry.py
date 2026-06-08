import urllib.request
import urllib.parse
import re
import http.cookiejar

def publish_to_rentry(markdown_content, custom_url=""):
    url = "https://rentry.co"
    
    # Set up cookie jar to handle session/CSRF cookies
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    # 1. Fetch homepage to get CSRF token and cookies
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    
    try:
        with opener.open(req) as response:
            html = response.read().decode('utf-8')
            
        # Find CSRF token in HTML
        csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
        if not csrf_match:
            print("Failed to find CSRF token on rentry.co")
            return None
            
        csrf_token = csrf_match.group(1)
        
        # 2. Prepare POST data
        post_data = {
            'csrfmiddlewaretoken': csrf_token,
            'text': markdown_content,
            'url': custom_url,
            'edit_code': 'kesher123'
        }
        
        # Encode POST data
        encoded_data = urllib.parse.urlencode(post_data).encode('utf-8')
        
        # Post to rentry.co (Rentry handles creation on the root / path or /api/new)
        # The main form action points to '/'
        post_req = urllib.request.Request(
            url,
            data=encoded_data,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://rentry.co/',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        
        with opener.open(post_req) as response:
            final_url = response.geturl()
            # If successfully redirected to the newly created page
            if final_url != "https://rentry.co" and final_url != "https://rentry.co/":
                return final_url
            else:
                # Sometimes it returns 200 with error messages in the body
                body = response.read().decode('utf-8')
                print("Creation failed or returned to homepage. Response snippet:")
                print(body[:500])
                
    except Exception as e:
        print(f"Error during Rentry publication: {e}")
        
    return None

if __name__ == "__main__":
    markdown = """# משאבי חינוך, זוגיות וגישור משפחתי באשדוד

מדריך משאבים מקצועי ומאמרים מומלצים לתושבי אשדוד והסביבה בתחומי המשפחה, ההורות והטיפול הזוגי.

---

## קישורים מומלצים לקליניקה של שירה סהרוני:

* 👩‍❤️‍👨 **ייעוץ זוגי מקצועי:** [יועצת זוגית באשדוד מומלצת](https://kesher.saharoni.com) — תהליך ממוקד לשיפור התקשורת ושיקום הקשר.
* 👨‍👩‍👧‍👦 **הדרכת הורים מוסמכת:** [הדרכת הורים ADHD אשדוד](https://kesher.saharoni.com/services/parenting) — ליווי וכלים פרקטיים להורים לילדים בעלי הפרעות קשב וריכוז.
* 🤝 **גישור וגירושין בהסכמה:** [מגשרת משפחתית אשדוד](https://kesher.saharoni.com/services/mediation) — פתרון סכסוכים ובניית הסכמים הוגנים מחוץ לכותלי בית המשפט.

---

## מאמרים נבחרים לקריאה:

1. **זוגיות ומשפחה:** [כיצד לבנות זוגיות בריאה ללא פחד משחזור דפוסי העבר?](https://kesher.saharoni.com/blog)
2. **התמודדות עם ילדים:** [איך להציב גבולות לילדים בצורה מכבדת ללא עונשים?](https://kesher.saharoni.com/blog)
3. **גישור וירושות:** [גישור במלחמות ירושה וסכסוכים משפחתיים](https://kesher.saharoni.com/blog)

*הקליניקה ממוקמת באשדוד ומציעה גם פגישות וידאו (אונליין) לכל רחבי הארץ.*
"""
    
    # Attempt to publish with a random or clean URL prefix
    import random
    rand_suffix = random.randint(1000, 9999)
    custom_url = f"kesher-seo-{rand_suffix}"
    
    print(f"Attempting to publish to rentry.co under: {custom_url}")
    result_url = publish_to_rentry(markdown, custom_url)
    if result_url:
        print(f"Successfully published backlink page on Rentry: {result_url}")
    else:
        print("Retrying without custom URL...")
        result_url = publish_to_rentry(markdown)
        if result_url:
            print(f"Successfully published backlink page on Rentry (automatic URL): {result_url}")
        else:
            print("Failed to publish on Rentry.")
