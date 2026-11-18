# KESHER — תחום ליווי כלכלי לזוגות ומשפחות

**מצב נכון ל־18.11.2026: התחום פורסם בייצור; בעל האתר מסר כי בדק את התוכן והשירות עם שירה וקיבל את אישורה. אין קמפיין PPC פעיל או מתוכנן כעת.**

## אישור תוכן והיקף שירות
- ב־18.11.2026 בעל האתר הודיע בשיחה כי בדק עם שירה את התוכן, והוא מאושר. זהו אישור שהועבר באמצעות בעל האתר, לא מסמך חתום של שירה.
- התוכן מציג חינוך פיננסי, התנהלות תקציב משפחתי ושיח זוגי סביב כסף. אין להציגו כייעוץ השקעות, מס, פנסיה, הסדר חובות או ייעוץ משפטי.
- אין צורך להחזיר את ה־PR למצב Draft. אין להפוך פסקאות מאושרות לאמירות על הכשרה או רישוי שלא אומתו בנפרד.

## נכסים קיימים באתר
- שירות: https://kesher.saharoni.com/services/family-financial-guidance
- מרכז ידע: https://kesher.saharoni.com/blog/category/family-finances
- 17 מאמרים חדשים במקור src/data/financialGuidancePosts.json, ו־3 מאמרים ותיקים המשולבים ברשימת המרכז בלי לשנות את גופי המאמרים החתומים.
- 17 איורי SVG למאמרים, 3 איורים לעמודי השירות והנחיתה.
- שני כלים חינמיים: /downloads/financial/money-conversation-worksheet.html ו־/downloads/financial/family-budget-template.csv
- שתי כתובות PPC קיימות, /financial-guidance-couples ו־/family-budget-guidance: `noindex, follow`, אינן ב־Sitemap. **אין להפעיל קמפיין** עד בקשה מפורשת חדשה מבעל האתר.

## ראיות איכות ופרסום
- פריסת Cloudflare ל־main הצליחה ב־18.11.2026; לאחר הבדיקות היא הייתה ב־SHA `f7c28589c94f515ef57b19eb3751512de63a567d` (ריצת Deploy 44284304349).
- CI של אותה גרסה עבר (44283911943); סך 167 בדיקות דפדפן עברו ו־1 דולגה במכוון. נבדקו 265 נתיבי HTML מוכנים ל־SEO.
- בבדיקות ה־E2E מכוסים 22 עמודי שירות/מרכז ידע/מאמרים, שני דפי PPC, קישורי קביעת פגישה, כתובות קנוניות, נתונים מובנים, מפת אתר, קבצי הורדה, תמונות ורוחב נייד.
- הפניה אמיתית לתיבת הדואר/פגישה בקלנדר וקליטת אירוע המרה במערכת Analytics **לא נבדקו מקצה לקצה בשירות חי**. אין לטעון אחרת.
- מפת אתר ו־HTML מוכנים לאינדוקס אינם הוכחה שגוגל סרק או אינדקס את הדפים. יש להשתמש בנתוני Search Console כדי לדעת את מצבם.

## מסלול אורגני בלבד — תוכנית מדידה
1. לחבר חשבון Google Search Console של הנכס למערכת המדידה הזמינה, ככל שההרשאות מאפשרות; לוודא שקובץ `https://kesher.saharoni.com/sitemap.xml` מתקבל בדוח Sitemaps. אין להגיש שוב ושוב ללא צורך.
2. לבדוק באמצעות URL Inspection את עמוד השירות, מרכז הידע ומדגם מייצג של מאמרים מכל אחד מארבעת אשכולות הנושא. להבחין בין `Indexed`, `Crawled — currently not indexed` ו־`Discovered — currently not indexed`.
3. לשמור נקודת התחלה לפי URL ושאילתה: impressions, clicks, CTR, average position, ומצב אינדוקס. להפריד את תחום כלכלת המשפחה מהנושאים האחרים של אתר קשר.
4. פעם בשבוע בחודש הראשון: לעקוב אחר נתוני Search Console שזמינים בפועל, שגיאות אינדוקס וקישורים שבורים; לבצע שינויים רק בהתאם לשאילתות ולפערים אמיתיים.
5. לאחר 28 ימים להשוות למצב ההתחלתי. לא להסיק שהשינויים תרמו לשיפור אם אין מספיק נתוני חשיפות/קליקים או ללא קבוצת השוואה מתאימה.
6. לשמור על פרטיות: אין לשגר מספרי חשבון, חובות, מצב זוגי או הודעות חופשיות ל־Analytics/תגי פרסום.

## כללי SEO/GEO
- כותרות ותשובה תמציתית בראש המאמר, הסברים מקוריים, מקורות ניתנים לבדיקת קישור, היררכיה סמנטית, קישורים פנימיים נוחים ועיצוב RTL.
- JSON-LD הוא מידע מובנה המסייע להבנה, **לא הבטחה** לתוצאות עשירות או לאזכור במנועי AI. אין לייצר תוכן מלאכותי רק לצורך "אופטימיזציה ל־AI".
- דפי נחיתה ממומנים נשארים מחוץ ל־Sitemap וב־noindex, גם בזמן שלא פועלות מודעות.

## מקורות עבודה רשמיים
- Google Search Central — AI features: https://developers.google.com/search/docs/appearance/ai-features
- Google Search Central — guidance for generative AI: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- Search Console — Sitemaps report: https://support.google.com/webmasters/answer/7451001
- Google Search Central — Sitemap and indexing: https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
