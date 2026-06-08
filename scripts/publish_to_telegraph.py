import urllib.request
import json

# Telegraph API endpoint
CREATE_PAGE_URL = "https://api.telegra.ph/createPage"

# We create a temporary session token using createAccount first
def get_access_token():
    url = "https://api.telegra.ph/createAccount?short_name=ShiraSaharoni&author_name=Shira%20Saharoni&author_url=https://kesher.saharoni.com"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            if res.get("ok"):
                return res["result"]["access_token"]
    except Exception as e:
        print(f"Error creating account: {e}")
    return None

def publish_article(access_token, title, content_nodes):
    data = {
        "access_token": access_token,
        "title": title,
        "author_name": "שירה סהרוני — ייעוץ זוגי והדרכת הורים",
        "author_url": "https://kesher.saharoni.com",
        "content": json.dumps(content_nodes),
        "return_content": True
    }
    
    # Send POST request
    req_data = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(CREATE_PAGE_URL, data=req_data, headers={
        'User-Agent': 'Mozilla/5.0',
        'Content-Type': 'application/x-www-form-urlencoded'
    })
    
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            if res.get("ok"):
                return res["result"]["url"]
            else:
                print("Error from Telegraph:", res)
    except Exception as e:
        print(f"Error publishing: {e}")
    return None

if __name__ == "__main__":
    token = get_access_token()
    if not token:
        print("Failed to get access token.")
        exit(1)
        
    print(f"Obtained Telegraph session token.")
    
    # Define articles content using Telegraph's DOM nodes format
    # Tag structure: [{"tag": "p", "children": ["text", {"tag": "a", "attrs": {"href": "..."}, "children": ["anchor"]}]}]
    articles = [
        {
            "title": "מתי כדאי לפנות לייעוץ זוגי ואיך לבחור יועצת זוגית באשדוד",
            "content": [
                {"tag": "p", "children": [
                    "שנים של חיים משותפים מביאות איתן לא פעם אתגרים מורכבים. שחיקה יומיומית, קשיים בתקשורת או שינויים במבנה המשפחתי עלולים ליצור מרחק בין בני הזוג. במקרים רבים, זוגות מוצאים את עצמם בלולאה אינסופית של ויכוחים מבלי להגיע לפתרון."
                ]},
                {"tag": "p", "children": [
                    "אם אתם מחפשים ",
                    {"tag": "a", "attrs": {"href": "https://kesher.saharoni.com"}, "children": ["יועצת זוגית באשדוד מומלצת"]},
                    ", חשוב להבין שפנייה לייעוץ היא סימן לעוצמה ורצון לשפר את איכות החיים המשותפת, ולא הודאה בכישלון."
                ]},
                {"tag": "h3", "children": ["מתי כדאי לפנות לייעוץ זוגי?"]},
                {"tag": "p", "children": [
                    "1. כשיש תחושת שחיקה וריחוק: מרגישים שאתם חיים כמו שותפים לדירה ולא כבני זוג? זהו אחד הסימנים לצורך בחידוש החיבור הרגשי."
                ]},
                {"tag": "p", "children": [
                    "2. ויכוחים חוזרים על אותם נושאים: כסף, חינוך הילדים, מטלות הבית — כשהנושאים הללו הופכים לזירת מלחמה קבועה."
                ]},
                {"tag": "p", "children": [
                    "3. משבר אמון: לאחר בגידה, הסתרת סודות או פגיעה קשה באמון ההדדי, ליווי מקצועי הוא כמעט הכרחי כדי לבנות את היסודות מחדש."
                ]},
                {"tag": "h3", "children": ["איך בוחרים את המלווה המתאים?"]},
                {"tag": "p", "children": [
                    "כשמחפשים תמיכה מקצועית באזור המגורים שלכם, כגון ",
                    {"tag": "a", "attrs": {"href": "https://kesher.saharoni.com/services/couples"}, "children": ["ייעוץ זוגי באשדוד"]},
                    ", כדאי לשים לב להסמכה של המטפלת, לגישה הטיפולית שלה, ובעיקר לחיבור הבינאישי שנוצר איתה כבר בפגישה הראשונה."
                ]}
            ]
        },
        {
            "title": "הדרכת הורים לילדים עם הפרעות קשב וריכוז ADHD באשדוד",
            "content": [
                {"tag": "p", "children": [
                    "גידול ילדים הוא משימה מאתגרת בפני עצמה, אך כאשר מתווספת לתמונה אבחנת קשב וריכוז (ADHD), ההתמודדות היומיומית הופכת מורכבת בהרבה. הורים רבים מוצאים את עצמם בעומס רגשי מתמיד, מתוסכלים מהתפרצויות זעם ומחוסר שיתוף פעולה במטלות פשוטות כמו התארגנות בבוקר או הכנת שיעורי בית."
                ]},
                {"tag": "p", "children": [
                    "לשם כך נועדה ",
                    {"tag": "a", "attrs": {"href": "https://kesher.saharoni.com/services/parenting"}, "children": ["הדרכת הורים ADHD אשדוד"]},
                    " — להעניק להורים את הכלים הפרקטיים להתמודד עם המאפיינים הייחודיים של הילד, ללא צורך במאבקי כוח בלתי פוסקים או עונשים שרק מגבירים את התסכול."
                ]},
                {"tag": "h3", "children": ["מה נותנת לכם הדרכת הורים מקצועית?"]},
                {"tag": "p", "children": [
                    "* הבנה מעמיקה של עולמו של הילד: מה שנראה לעיתים כעקשנות או חוצפה הוא לרוב קושי אמיתי בוויסות רגשי או בניהול זמן."
                ]},
                {"tag": "p", "children": [
                    "* בניית שגרה מותאמת: כלים לעיצוב סדר יום ברור ומובנה שמפחית חרדה ומגדיל את שיתוף הפעולה."
                ]},
                {"tag": "p", "children": [
                    "* חיזוק הקשר ההורי: כיצד להוביל את הבית מתוך סמכות הורית בריאה, חמלה וחיבור רגשי חזק."
                ]},
                {"tag": "p", "children": [
                    "אם אתם מתמודדים עם אתגרים דומים ומחפשים ליווי מקצועי שיחזיר את השקט והביטחון המשפחתי, מומלץ לפנות למנחת הורים מנוסה המכירה את הקשיים הללו מקרוב."
                ]}
            ]
        }
    ]
    
    for article in articles:
        url = publish_article(token, article["title"], article["content"])
        if url:
            print(f"Published successfully to Telegraph: {url}")
        else:
            print(f"Failed to publish: {article['title']}")
