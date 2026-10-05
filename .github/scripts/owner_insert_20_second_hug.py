from pathlib import Path
import json

POSTS = Path("src/data/posts.json")
SLUG = "20-second-hug-relationship-stress"

raw = POSTS.read_text(encoding="utf-8")
if f'"slug": "{SLUG}"' in raw or f'"id": "{SLUG}"' in raw:
    raise SystemExit(f"duplicate slug/id already present: {SLUG}")
if not raw.lstrip().startswith("["):
    raise SystemExit("posts.json root is not an array; refusing mutation")

content = """<p><strong>מחבקים את בן או בת הזוג לשנייה בדרך למטבח?</strong> ברוב הבתים זה קורה על אוטומט: נכנסים, אומרים שלום, חצי חיבוק — ומיד עוברים לילדים, לטלפון, לארוחת ערב ולכל מה שחיכה מאז הבוקר. ואז מגיע הטיפ שרץ ברשת: חיבוק של 20 שניות מוריד סטרס, מעלה אוקסיטוצין ואפילו משפיע על לחץ הדם.</p>
<p>יש כאן בסיס מחקרי מעניין, אבל כדאי לדייק. אין הוכחה ל"מתג" שנדלק בדיוק בשנייה ה־20, ואין בסיס טוב לטענה שחיבוק של שתיים או שלוש שניות הוא רק נימוס ושאין לו שום השפעה. מה שכן יש: מחקרים שמראים שמגע חם ותומך בין בני זוג יכול להיות קשור לתגובה גופנית רגועה יותר במצבי לחץ.</p>
<h3>אז מאיפה הגיעו 20 השניות?</h3>
<p>במחקר מעבדה של Karen Grewen, Bobbi Anderson, Susan Girdler ו־Kathleen Light מאוניברסיטת צפון קרוליינה, זוגות שחיו יחד חולקו לשתי קבוצות לפני משימת לחץ. בקבוצת המגע החם בני הזוג החזיקו ידיים במשך עשר דקות בזמן צפייה בסרטון רומנטי, ולאחר מכן התחבקו במשך 20 שניות. קבוצת הביקורת פשוט ישבה בשקט.</p>
<p>לאחר מכן המשתתפים נדרשו לבצע משימת דיבור מלחיצה. אצל מי שקיבלו את המגע הזוגי לפני המשימה, העלייה בלחץ הדם ובדופק הייתה מתונה יותר. זה לא אומר שחיבוק של 20 שניות הוא טיפול בלחץ דם. זה כן אומר שמגע זוגי חם, כחלק מפרוטוקול של קרבה, נקשר לתגובה קרדיווסקולרית רגועה יותר בזמן סטרס.</p>
<p><a href="https://pubmed.ncbi.nlm.nih.gov/15206831/" target="_blank" rel="noopener noreferrer">למחקר ב־PubMed: Warm partner contact is related to lower cardiovascular reactivity</a>.</p>
<h3>ומה לגבי אוקסיטוצין?</h3>
<p>במחקר נוסף של Grewen, Girdler, Amico ו־Light, 38 זוגות עברו מנוחה, עשר דקות של מגע חם עם בן או בת הזוג, ואז מנוחה נוספת. תמיכה זוגית גבוהה יותר הייתה קשורה לרמות אוקסיטוצין גבוהות יותר לאורך הפרוטוקול. אצל נשים היא נקשרה גם ללחץ דם סיסטולי נמוך יותר במנוחה שלאחר המגע.</p>
<p>גם כאן חשוב לשמור על דיוק: המחקר לא מצא "קפיצה" אוטומטית באוקסיטוצין בשנייה ה־20. הוא מחזק תמונה רחבה יותר שבה קשר תומך ומגע רצוי הם חלק ממערכת של קרבה, ביטחון וויסות.</p>
<p><a href="https://pubmed.ncbi.nlm.nih.gov/16046364/" target="_blank" rel="noopener noreferrer">למחקר ב־PubMed: Effects of partner support on resting oxytocin, cortisol, norepinephrine, and blood pressure</a>.</p>
<h3>ומה קורה מחוץ למעבדה?</h3>
<p>מחקר נוסף בהובלת Kathleen Light מצא שבקרב נשים לפני גיל המעבר, תדירות גבוהה יותר של חיבוקים עם בן הזוג הייתה קשורה לרמות אוקסיטוצין גבוהות יותר וללחץ דם ודופק נמוכים יותר במנוחה. זה קשר סטטיסטי — לא הוכחה שכל חיבוק מוריד מיד מספר מסוים במד לחץ הדם — אבל הוא בהחלט מצטרף לתמונה.</p>
<p><a href="https://pubmed.ncbi.nlm.nih.gov/15740822/" target="_blank" rel="noopener noreferrer">למחקר ב־PubMed: More frequent partner hugs and higher oxytocin levels are linked to lower blood pressure and heart rate</a>.</p>
<h3>אז למה בכל זאת שווה לנסות חיבוק של 20 שניות?</h3>
<p>לא בגלל קסם ביולוגי במספר 20. בגלל ש־20 שניות הן מספיק זמן כדי להפוך מחווה אוטומטית לעצירה אמיתית.</p>
<p>יש הבדל בין "היי, מה נשמע?" תוך כדי שמורידים נעליים ובודקים ווטסאפ, לבין רגע שבו שני בני הזוג עוצרים, מניחים את הטלפון, מתחבקים ונשארים שם עוד קצת. מבחינה זוגית, זה מסר אחר לגמרי: <strong>אני כאן. ראיתי אותך. לפני המשימות — אנחנו נפגשים.</strong></p>
<h3>האתגר: 20 שניות בכניסה הביתה</h3>
<p>נסו במשך שבוע טקס קטן אחד:</p>
<ul>
<li>כשאחד מכם נכנס הביתה, עוצרים לפני שנכנסים ישר למשימות.</li>
<li>מניחים את הטלפון לרגע.</li>
<li>מתחבקים בהסכמה במשך בערך 20 שניות.</li>
<li>לא פותרים בזמן הזה שום בעיה.</li>
<li>לא שואלים מי אוסף מחר, מה קונים בסופר ולמה לא ענית קודם.</li>
</ul>
<p>המטרה אינה לבדוק אם "עבד" או למדוד אוקסיטוצין. המטרה היא ליצור רגע קבוע של מעבר: מהכביש לבית, מהעבודה לזוגיות, מהמרוץ לקשר.</p>
<h3>ומה אם אחד מאיתנו לא אוהב חיבוקים ארוכים?</h3>
<p>לא כופים מגע בשם המדע. מגע מרגיע רק כשהוא רצוי ונעים לשני הצדדים. אפשר לבחור טקס קרבה אחר: להחזיק ידיים, לשבת צמוד דקה, להניח יד על הכתף או פשוט לעצור ולהסתכל אחד על השנייה בלי מסך באמצע.</p>
<p>המטרה היא לא לעמוד בחוק של 20 שניות. המטרה היא להזכיר לגוף ולזוגיות שיש כאן קשר — לא רק ניהול משימות משותף.</p>
<h3>חשוב: חיבוק אינו טיפול רפואי</h3>
<p>חיבוק אינו טיפול ביתר לחץ דם, חרדה או כל מצב רפואי אחר, והמחקרים האלה אינם סיבה להפסיק טיפול רפואי או פסיכולוגי. הם כן מוסיפים עוד חתיכה לפאזל שמראה שקשרים תומכים ומגע רצוי יכולים להיות חלק מאורח חיים שעוזר להתמודד טוב יותר עם סטרס.</p>
<h3>השורה התחתונה</h3>
<p>אל תחפשו את השנייה שבה "האוקסיטוצין נדלק". חפשו את הרגע שבו אתם באמת עוצרים ונפגשים.</p>
<p>הערב, כשאתם חוזרים הביתה, נסו חיבוק אחד של 20 שניות. בלי טלפון. בלי לפתור. בלי לרוץ למשימה הבאה. רק לתת לגוף ולזוגיות רגע להגיע הביתה יחד.</p>
<p>אם העומס והסטרס כבר אוכלים את הקרבה, <a href="/services/couples">ייעוץ זוגי</a> יכול לעזור לבנות מחדש טקסים של קשר, תקשורת וביטחון — באשדוד או אונליין.</p>"""

article = {
    "id": SLUG,
    "slug": SLUG,
    "title": "חיבוק של 20 שניות: מה המחקר באמת אומר על סטרס, לחץ דם וזוגיות",
    "excerpt": "האם חיבוק של 20 שניות באמת מוריד סטרס? מחקרי המעבדה של ד״ר קתלין לייט ועמיתיה מצביעים על קשר בין מגע זוגי חם לתגובה רגועה יותר — אבל המציאות מדויקת יותר מהמיתוס שרץ ברשת.",
    "content": content,
    "date": "2026-10-05",
    "updatedAt": "2026-10-05",
    "category": "זוגיות",
    "subcategory": "קרבה וויסות",
    "tags": [
        "חיבוק 20 שניות",
        "סטרס בזוגיות",
        "אוקסיטוצין",
        "ייעוץ זוגי"
    ],
    "author": "שירה סהרוני",
    "serviceUrl": "/services/couples",
    "serviceLabel": "ייעוץ זוגי",
    "directAnswer": "חיבוק של 20 שניות אינו מספר קסם, אבל מחקרים על מגע חם בין בני זוג מצאו קשר לתגובה קרדיווסקולרית מתונה יותר בזמן סטרס ולמדדים הקשורים באוקסיטוצין. בפועל, 20 שניות הן דרך פשוטה לעצור, ליצור מגע רצוי ולתת לגוף ולזוגיות רגע של קרבה.",
    "evidence": [
        {
            "title": "Warm partner contact is related to lower cardiovascular reactivity",
            "source": "Behavioral Medicine / PubMed",
            "url": "https://pubmed.ncbi.nlm.nih.gov/15206831/",
            "note": "פרוטוקול של מגע חם שכלל חיבוק של 20 שניות נקשר לעלייה מתונה יותר בלחץ דם ובדופק בזמן משימת לחץ."
        },
        {
            "title": "Effects of partner support on resting oxytocin, cortisol, norepinephrine, and blood pressure",
            "source": "Psychosomatic Medicine / PubMed",
            "url": "https://pubmed.ncbi.nlm.nih.gov/16046364/",
            "note": "תמיכה זוגית גבוהה יותר נקשרה לרמות אוקסיטוצין גבוהות יותר; אצל נשים נמצאה גם זיקה ללחץ דם סיסטולי נמוך יותר אחרי מגע חם."
        },
        {
            "title": "More frequent partner hugs and higher oxytocin levels are linked to lower blood pressure and heart rate",
            "source": "Biological Psychology / PubMed",
            "url": "https://pubmed.ncbi.nlm.nih.gov/15740822/",
            "note": "תדירות גבוהה יותר של חיבוקים עם בן הזוג נקשרה אצל נשים לפני גיל המעבר לאוקסיטוצין גבוה יותר וללחץ דם ודופק נמוכים יותר במנוחה."
        }
    ],
    "controllerManaged": False,
    "videoTitle": "חיבוק של 20 שניות באמת מוריד סטרס? מה המחקר אומר",
    "videoTags": [
        "חיבוק 20 שניות",
        "סטרס בזוגיות",
        "אוקסיטוצין",
        "זוגיות"
    ],
    "shortTitle": "חיבוק של 20 שניות: לא קסם — אבל כן שווה לנסות",
    "shortTags": [
        "חיבוק 20 שניות",
        "זוגיות",
        "סטרס",
        "אוקסיטוצין"
    ],
    "shortHook": "מחבקים לשנייה בדרך למטבח? הנה מה שבאמת מצאו במחקר על חיבוק של 20 שניות.",
    "image": "/images/generated/blog/marriage-after-trust-leak.jpg",
    "imageAlt": "זוג ברגע שקט של קרבה וחיבור",
    "imageProvider": "Local",
    "imageSourceUrl": "local://public/images/generated/blog/marriage-after-trust-leak.jpg",
    "imageIsFallback": True
}

first = raw.index("[")
block = json.dumps(article, ensure_ascii=False, indent=2)
block = "\n".join("  " + line for line in block.splitlines())
updated = raw[: first + 1] + "\n" + block + "," + raw[first + 1 :]
parsed = json.loads(updated)

matches = [p for p in parsed if isinstance(p, dict) and p.get("slug") == SLUG]
if len(matches) != 1:
    raise SystemExit(f"expected exactly one inserted slug, got {len(matches)}")

POSTS.write_text(updated, encoding="utf-8")
print(f"inserted {SLUG}; posts={len(parsed)}")
