# דוח מצב טכני: מוכנות AEO/GEO באתר Kesher (kesher.saharoni.com)

## 1. תקציר מנהלים

אתר **קשר** (שירה סהרוני) מציג תשתית טכנית איכותית ומתקדמת בהרבה מהמקובל באתרי ייעוץ פרטיים בישראל:
- **רינדור סטטי מלא (Prerender SSG):** כל עמוד מרונדר ל-HTML סטטי מלא באמצעות Playwright/Chromium לפני פריסה.
- **הפרדה עקרונית של בוטים:** `robots.txt` מאפשר סריקת אחזור וחיפוש AI וחוסם אימון מודלים גנרי.
- **אוטומציה וולידציה קפדנית:** מחסומי תוכן ובטיחות תביעות (Claim Quality Gate) אוכפים סטנדרטים לשוניים ותוכניים.

עם זאת, לצורך הפיכה למקור מועדף ואמין במנועי מענה (Google AI Overviews, ChatGPT Search, Perplexity):
- **זהות הישות (Entity) מפוצלת:** מופעי ה-`Person` אינם מקושרים בעקביות ל-`@id` קנוני יחיד.
- **עדכניות מלאכותית / חוסר הפרדה של תאריכים:** `dateModified` זהה ל-`datePublished`.
- **מבנה תוכן שאינו מותאם לאחזור פסקאות (Passage Retrieval):** חסר BLUF/תשובה ממוקדת בתחילת המאמר, מבנה פסקאות עצמאי, וקישוריות פנימית דו-כיוונית בין עמודי שירות לעמודי מאמר.

---

## 2. ביקורת זחילה, אחזור ומדיניות בוטים (Crawl & Retrieval Eligibility)

נבדק קובץ המקור: [`public/robots.txt`](file:///Users/ninja/Documents/Kesher/public/robots.txt).

### 2.1 בוטים מאושרים לאחזור וחיפוש AI (Allow)
- `OAI-SearchBot` — חיפוש חי עבור SearchGPT / ChatGPT Search.
- `ChatGPT-User` — אחזור בזמן אמת של שאילתות משתמש ב-ChatGPT.
- `PerplexityBot` — סריקה ואחזור תשובות עבור מנוע Perplexity.
- `Claude-SearchBot` & `Claude-User` — אחזור וחיפוש עבור Anthropic Claude.
- `Googlebot` & `Bingbot` — מנועי חיפוש מסורתיים ו-AI Overviews / Copilot.

### 2.2 בוטים חסומים לאימון מודלים (Disallow)
- `GPTBot` — איסוף נתונים גולמי לאימון מודלים של OpenAI.
- `ClaudeBot` — איסוף נתונים גולמי לאימון Claude.
- `Google-Extended` — אימון Gemini / Vertex AI על תכני האתר.
- `CCBot` — איסוף Common Crawl.

**מסקנה טכנית:** ההבחנה בין **בוטי אחזור חיפוש** לבין **בוטי אימון מודלים** מיושמת באופן מדויק. אין צורך בשינוי ב-`robots.txt` בשלב זה.

---

## 3. ארכיטקטורת רינדור וזמינות HTML (Rendering & Prerender Pipeline)

- **מערכת הבנייה:** React 19, Vite 8, React Router 7, Cloudflare Pages.
- **מנגנון Prerender:** נבדק [`scripts/prerender.cjs`](file:///Users/ninja/Documents/Kesher/scripts/prerender.cjs).
  - לאחר `vite build`, מופעל שרת תצוגה מקדימה מקומי על פורט 4179.
  - Playwright מפעיל מופע Chromium אמיתי, מדלג על נכסים כבדים (תמונות, וידאו, סקריפטים של צד שלישי), ומבקר בכל הנתיבים הסטטיים והמאמרים המפורסמים.
  - הסקריפט ממתין לאלמנט `#main-content h1` ול-`link[rel="canonical"]` לפני לכידת ה-DOM באמצעות `page.content()`.
  - התוצאה נכתבת כקובצי HTML מלאים תחת `dist/` (לרבות ספריות אינדקס עבור נתיבי בלוג בעברית תואמי Cloudflare Pages).
- **בדיקת איכות Prerender:** נבדק [`scripts/verify-dist.cjs`](file:///Users/ninja/Documents/Kesher/scripts/verify-dist.cjs).
  - מוודא קיום קובץ HTML עבור כל נתיב מאושר.
  - מוודא קיום בדיוק תגית `<h1>` אחת, בדיוק תגית `description` אחת ובדיוק `canonical` יחיד.
  - מוודא שדף `404.html` כולל `noindex, nofollow`.

**מסקנה טכנית:** תכני האתר, המטא-תגיות ונתוני ה-JSON-LD זמינים ב-HTML סטטי טהור ואינם תלויים בביצוע JavaScript אצל מנועי החיפוש וה-AI.

---

## 4. אותות אינדוקס ומטא-דאטה (Indexing Signals)

נבדקו: [`src/components/SEO/MetaTags.tsx`](file:///Users/ninja/Documents/Kesher/src/components/SEO/MetaTags.tsx), [`scripts/generate-sitemap.cjs`](file:///Users/ninja/Documents/Kesher/scripts/generate-sitemap.cjs).

| אות אינדוקס | סטטוס קיים | פער / הזדמנות AEO |
|---|---|---|
| **Canonical** | תקין, מנוהל בכל עמוד ונאכף ב-`verify-dist.cjs`. | אין פער. |
| **Robots Meta** | תקין: מוגדר `noindex, nofollow` לדפי תודה ו-404. | אין פער. |
| **Language & Locale** | מוגדר `lang="he"` ב-`index.html`, `og:locale` מוגדר `he_IL`. | אין פער. |
| **Sitemap** | אוטומטי (`sitemap.xml`) עבור כל 24 הנתיבים הסטטיים ו-74 המאמרים. | דפים סטטיים (כולל שירות) אינם מקבלים `lastmod`. |
| **Date Modified** | קיים רק `date` בודד למאמר. `dateModified` בסכמה זהה ל-`datePublished`. | מנועי AI אינם מקבלים אינדיקציה מהימנה לרענון תוכן אמיתי. |
| **Author attribution** | תגית `author: שירה סהרוני` מוגדרת במטא. | אין קישור ישיר לפרופיל ישות במטא (`rel="author"`). |

---

## 5. ביקורת מידע מובנה (Structured Data Audit)

נבדקו הקומפוננטה [`src/components/SEO/SchemaOrg.tsx`](file:///Users/ninja/Documents/Kesher/src/components/SEO/SchemaOrg.tsx) והסכמות בעמודי האתר.

### 5.1 ממצאים עיקריים
1. **פיצול ישות Person (שירה סהרוני):**
   - בדף הבית (`Home.tsx`): מוגדרת ישות קנונית עם מזהה קבוע `@id: "https://kesher.saharoni.com/#shira"`.
   - בדף אודות (`AboutPage.tsx`): ישות `ProfilePage` מחזיקה אובייקט `Person` אנונימי (ללא `@id` כלל!).
   - בדפי המאמרים (`BlogPost.tsx`): מוגדר אובייקט `Person` פנימי עם `url: "https://kesher.saharoni.com"` (דף הבית) במקום הפניה למזהה הקנוני `/#shira` או לדף האודות `/about`.
2. **פיצול ישות עסקית (LocalBusiness):**
   - מוגדר `@id: "https://kesher.saharoni.com/#business"` בדף הבית ובעמודי השירות.
   - בדף נחיתה אשדוד (`CouplesCounselingAshdodPage.tsx`): מוגדרת ישות מסוג `['LocalBusiness', 'ProfessionalService']` עם מזהה `...#service`, ובתוכה שדה `provider` המצביע שוב על `/#business` — כפילות לא עקבית של ישות העסק.
3. **גרף ישויות מנותק במאמרים (`BlogPost.tsx`):**
   - אובייקט ה-`Article` חסר `@id` מוגדר (למשל: `.../blog/<id>#article`).
   - ה-`publisher` מוגדר כאובייקט `Organization` אנונימי חדש, במקום להפנות ל-`{"@id": "https://kesher.saharoni.com/#business"}`.
4. **עמודי שירות (Service):**
   - מצביעים על `provider: {"@id": ".../#business"}` אך אינם מקשרים ליועצת המבצעת (`provider` -> `employee` / `founder` -> `/#shira`).
   - רוב עמודי השירות חסרים בלוק `FAQPage` מובנה (קיים רק בייעוץ זוגי).

---

## 6. ביקורת מודל הנתונים של המאמרים (Article Model Audit)

נבדק קובץ המקור: [`src/data/posts.json`](file:///Users/ninja/Documents/Kesher/src/data/posts.json) וסקריפט המדיניות [`scripts/content-policy.cjs`](file:///Users/ninja/Documents/Kesher/scripts/content-policy.cjs).

- **סך הכל רשומות ב-`posts.json`:** 85.
- **מאמרים מפורסמים (עומדים בשער האיכות):** 74 מאמרים (לפחות 500 מילים ולפחות 5 כותרות `<h3>`).
- **טיוטות ישנות / לא מפורסמות:** 11 מאמרים (אינם נכללים ב-sitemap או ב-prerender).
- **מבנה רשומה קיים:**
  `id`, `title`, `excerpt`, `date`, `author`, `category`, `subcategory`, `readTime`, `content` (HTML), `image`, `imageAlt`, ושדות רשות: `serviceUrl`, `serviceLabel`, `slug`, `tags`, `video`.

### 6.2 הערכת כדאיות שדות עתידיים לשדרוג AEO
הערכה ביקורתית של שדות פוטנציאליים לפי 5 שאלות החובה:

| שדה מוצע | איזה בעיה זה פותר? | האם שדה חדש הכרחי? | האם מבנה תוכן קיים מספיק? | שינויי קוד נדרשים | נטל מיגרציה | המלצה |
|---|---|---|---|---|---|---|
| **`updatedAt`** | תאריך עדכון מהימן עבור מנועי חיפוש ו-AI. | **כן**. | לא — כיום יש רק `date` בודד. | עדכון `BlogPost.tsx` (dateModified), `generate-sitemap.cjs`, `validate-content.cjs`. | אפס. שדה אופציונלי; ברירת מחדל שווה ל-`date`. | **מאושר ליישום ב-Phase 1**. |
| **`directAnswer`** | תשובה ישירה (BLUF) של 40–60 מילים לשליפה על ידי AI Overviews / Featured Snippets. | **לא**. | **כן** — פסקה ראשונה ייעודית (Lead) ב-HTML של המאמר או שימוש מושכל ב-`excerpt`. | אין צורך בשדה נפרד, רק סטנדרט כתיבה ומבנה HTML. | אין נטל. | **לא להוסיף שדה; להשתמש במבנה תוכן**. |
| **`keyTakeaways`** | נקודות עיקריות בראש המאמר לתשובות מהירות. | **לא**. | **כן** — רשימת `<ul>` סמנטית תחת תת-כותרת תקנית `<h3>` בתוך גוף המאמר. | אין צורך בשינוי סכמה בקוד. | אין נטל. | **לא להוסיף שדה; מבנה תוכן קיים מספיק**. |
| **`expertInsight`** | עמדה אישית / תובנה קלינית של שירה. | **לא**. | **כן** — בלוק ציטוט `<blockquote>` או קופסת תובנה בתוכן. | עיצוב CSS בלבד למחלקת callout. | אין נטל. | **לא להוסיף שדה; שימוש ב-HTML סמנטי**. |
| **`evidence`** | מקורות מידע, מחקרים או אסמכתאות מקצועיות. | **לא**. | **כן** — קישורים פנימיים או סעיף מקורות סמנטי בסוף המאמר. | אין צורך בשדה מובנה. | מונע סיבוך JSON. | **לא להוסיף שדה; שימוש ב-HTML סמנטי**. |
| **`relatedQuestions`** | שאלות המשך טבעיות לחיפוש שיחתי. | **לא**. | **כן** — בלוק שאלות ותשובות בגוף המאמר עם סכמת FAQ אופציונלית. | אין צורך בשדה נפרד. | אין נטל. | **לא להוסיף שדה**. |
| **`relatedArticles`** | קישוריות פנימית מוגדרת בין מאמרים באותו אשכול. | **כן (מוגבל)**. | שילוב — עדיף קישורים פנימיים חיים בגוף הטקסט (Contextual Links). | ניתן לבצע חישוב אוטומטי לפי קטגוריה/תגיות במקום הזנה ידנית. | אין צורך בהזנה ידנית לכל 74 המאמרים. | **המלצה: מנגנון אוטומטי בקוד לפי subcategory/tags**. |
| **`topicCluster`** | סיווג נושאי אחיד במקום פיצול שדות. | **לא**. | שדה `subcategory` כבר קיים ב-43 מאמרים ומשמש בפועל כאשכול. | יישור קו של ערכי `subcategory` הקיימים. | השלמת `subcategory` ל-31 מאמרים חסרים. | **להשתמש ב-`subcategory` הקיים, לא ליצור שדה חדש**. |
| **`contentTier`** | הבחנה בין עמודי ליבה (Tier 1) למאמרי זנב (Tier 2/3). | **כן (תיעודי)**. | לא קיים כיום מנגנון עדיפות פנימי פרט ל-sitemap priority. | שימוש בקובץ קונפיגורציה חיצוני ולא כחלק מרשומת המאמר ב-`posts.json`. | אפס נטל על `posts.json`. | **להגדיר בקובץ ארכיטקטורה, לא ב-`posts.json`**. |
| **`needsExpertInput`** | סימון מאמר הדורש תובנה ראשונית משירה. | **כן (פנימי)**. | שדה ניהול תהליך עבודה. | שימושי רק בבקלוג ניהולי, לא צריך להגיע ל-production bundle. | שמירה ב-`docs/aeo/` ולא ב-`posts.json`. | **לנהל במסמכי AEO בלבד**. |

**עיקרון מנחה למודל הנתונים:** שמירה על מודל הנתונים הקטן והפשוט ביותר האפשרי. השדה היחיד הנדרש להוספה לקוד הליבה בעתיד הוא `updatedAt` (תאריך עדכון מהימן). כל שאר פונקציות ה-AEO ימומשו באמצעות מבנה HTML סמנטי סטנדרטי וקונפיגורציה חיצונית.
