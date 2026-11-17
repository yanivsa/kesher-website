# KESHER — תחום ליווי כלכלי לזוגות ומשפחות
**מועמד לפרסום, 17.11.2026; מחייב בקרת תוכן מקצועית ואישור שירה לפני מיזוג.**

## נכסים שבענף
- שירות: /services/family-financial-guidance
- מרכז מאמרים: /blog/category/family-finances
- דפי נחיתה /financial-guidance-couples, /family-budget-guidance — מחוץ לאינדקס
- 17 מאמרים חדשים ב־src/data/financialGuidancePosts.json, 3 מאמרים קיימים עם כתובת קנונית שמורה.
- 17 איורי SVG עצמאיים למאמרים, 3 איורי SVG לעמודים, תמונת רסטר קיימת לשיתוף ברשתות חברתיות.
- שני כלים להורדה: /downloads/financial/money-conversation-worksheet.html ו־/downloads/financial/family-budget-template.csv
- דפי שירות קשורים, Header, Footer ובלוג מקושרים לתחום החדש.

## עקרונות SEO ו־GEO
H1 ברור, תשובה תמציתית, קישורים פנימיים מהקשר, מחבר, מקור מקצועי חיצוני, היררכיית H3, והימנעות מהבטחות. JSON-LD: Article, Service, CollectionPage, BreadcrumbList לפי רכיבי האתר. מנגנוני Sitemap, Prerender, סיכומי מאמרים, רשימת נתיבים ו־llms.txt עודכנו. אין Schema שמבטיח אזכור בתשובות AI.
מקורות:
https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
https://pop.education.gov.il/tchumey_daat/financial-education/junior-high/curriculum/rationale/

## שערי איכות לפני פריסה
1. שירה מאשרת בכתב את הכשרתה כעוסקת בחינוך פיננסי, היקף השירות, מסלולים, תמחור (אם מוצג), זמינות ומיקום.
2. שירה מבקרת את כל 20 המאמרים, המידע והטון, כולל אישור שיוך המחבר בשמה. לא לבצע Merge לפני כן.
3. לפעול רק לאחר CI ו־Stability PR Validation ירוקים על אותו HEAD ומעבר רגרסיות קיימות.
4. לבצע npm run generate, npm run test:content, npm run test, npm run build, npm run verify:dist, npm run test:e2e; לשמור על מערכת ייצור המאמרים/הווידאו.
5. לבדוק 17 מאמרים ב־HTML סטטי: כותרת, canonical, תמונה, קישורים, ALT ו־Schema. דפי PPC חייבים noindex ואינם נכללים ב־Sitemap.
6. QA לנייד, RTL, נגישות, טפסים, WhatsApp, תורים, אירועי מדידה ואי־חשיפת מידע פיננסי במעקב. המרות קליק אינן זהות לפגישות שהתקיימו.
7. להפעיל גיליון CSV ב־Excel/Sheets ולוודא שבשורת sep=; היא הוראת מפריד שאינה שורת גיליון; הנוסחאות מפנות לשורות 2–16.
8. לא לפרסם המלצות השקעה, פנסיה, מס, משפט או הסדר חובות; כפייה כלכלית מחייבת מסלול סיוע בטוח.
9. לא לעלות בייצור לפני צילום מסך לכל עמוד, בדיקת זכויות תמונה, ניטור 404 ויכולת Rollback.

## מצב פרסום
ה־PR נפתח כ־Draft במכוון. ללא מיזוג ל־main וללא Deploy. קמפיינים ממומנים עדיין לא הופעלו; התקציב, חשבון Ads ופרטי השירות לא אושרו.
