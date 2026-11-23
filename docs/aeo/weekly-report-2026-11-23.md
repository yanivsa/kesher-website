# Weekly AEO Report — 2026-11-23

**אתר:** [kesher.saharoni.com](https://kesher.saharoni.com/)  
**עסק:** קשר - מרכז לייעוץ זוגי והדרכת הורים | שירה סהרוני  
**מאגר קוד:** `yanivsa/kesher-website`  
**תאריך דוח שבועי:** 23 בנובמבר 2026  
**סטטוס כללי:** תקין לחלוטין (100% Clean Technical Health), אפס נסיגות (Zero Regressions)  
**שער התרחבות שבועי:** **READY FOR JULES / BATCH 1 CONFIRMED IN ISSUE #848**

---

## 1. מרשם ה-Cohorts המנוטרים (Cohorts Monitored)

בביקורת השבועית נמדדו **3 Cohorts** הכוללים **14 כתובות URL** שנפרסו בפועל ל-production:

| Cohort | תאריך פריסה | ותק (שבועות/ימים) | URLs מנוטרים | שינויים שבוצעו | החלטה שבועית |
|---|---|---|---|---|---|
| **Cohort 0 (Pilot / Batch 0)** | 2026-09-15/16 | שבוע 10 (68 ימים) | • `/couples-counseling-ashdod`<br/>• `/services/gifted-parenting`<br/>• `/blog/gifted-adhd-executive-functions-struggle`<br/>• `/blog/newlywed-first-year-conflicts`<br/>• `/blog/returning-to-israel-after-relocation-relationship` | סכמת ישות קנונית (`#shira`, `#business`), תשובות ישירות BLUF, טבלת השוואת דפוסים, בלוק Evidence מחקרי ומשרד החינוך, מודל תאריכי אמת `updatedAt`. | **KEEP** (יציב לחלוטין, 0 נסיגות לאורך 68 ימי מעקב) |
| **Cohort 1 (Core Services Alignment)** | 2026-09-23 | שבוע 9 (61 ימים — חודשיים מלאים) | • `/services/couples`<br/>• `/services/mediation`<br/>• `/services/parenting`<br/>• `/services/premarital-first-year` | חידוד הגדרות שירות answer-first, הפרדת גישור מייעוץ זוגי, תיחום גבולות הדרכת הורים (ללא טיפול ישיר בילד), נרמול H1 וסכמה מול כוונת חיפוש. | **KEEP** (יציב לחלוטין, 0 נסיגות, בידול שירותים מלא) |
| **Cohort 2 (Parenting P1 Cluster)** | 2026-10-18 | שבוע 5 (36 ימים — עבר אבן דרך 30 יום) | • `/blog/prepare-for-first-grade`<br/>• `/blog/first-grade-readiness`<br/>• `/blog/potty-training-age-3-problems`<br/>• `/blog/nighttime-potty-training`<br/>• `/blog/potty-training-regression` | חמישה מאמרי אשכול הדרכת הורים עם `directAnswer` תמציתי ומסויג, 3 מקורות Evidence רשמיים (משרד הבריאות, משרד החינוך, AAP) לכל מאמר, קישור ל-`/services/parenting`. | **KEEP** (עבר בהצלחה 36 ימי הבשלה; בריאות טכנית מושלמת; אינדוקס יציב ב-sitemap; מעקב רציף לקראת ביקורת 60 יום) |

---

## 2. בריאות טכנית (Technical Health)

כל 14 הכתובות נבדקו ישירות מול סביבת הייצור החיה (`https://kesher.saharoni.com`):

- **HTTP Status:** `200 OK` ב-14 מתוך 14 הכתובות המנוטרות.
- **Canonical Tags:** 100% תגיות קנוניקל עצמיות (`1:1 self-canonical`) מדויקות ותואמות נתיב, ללא הפניות או שגיאות.
- **Robots / Indexability:** כל העמודים פתוחים לאינדוקס מלא. קובץ `robots.txt` מאפשר גישה מלאה לבוטי אחזור וחיפוש של AI (`OAI-SearchBot`, `ChatGPT-User`, `PerplexityBot`, `Claude-SearchBot`, `Googlebot`, `Bingbot`) וחוסם בוטי אימון בלבד (`GPTBot`, `ClaudeBot`, `Google-Extended`, `CCBot`).
- **Sitemap & Freshness:** מפת האתר (`sitemap.xml`) מגישה תאריכי `<lastmod>` אמינים ומדויקים (`2026-09-16` למאמרי הפיילוט, `2026-10-18` למאמרי ההורות של Cohort 2) ללא רענון תאריכים מזויף. עמודי שירות מוצגים ללא תאריך שגוי.
- **Structured Data:** גרף ה-JSON-LD תקין לחלוטין בכל 14 העמודים. ישות המחבר במאמרים מצביעה לעוגן הקנוני `/#shira`, ישות המוציא לאור / ספק השירות מצביעה ל-`/#business`. סכמות `FAQPage` ספקולטיביות אינן קיימות בעמודי פילאר.
- **Desktop & Mobile Rendering:** תקין לחלוטין. כיווניות עברית RTL מלאה, ללא גלישה אופקית (0px horizontal overflow), טבלאות נגישות ורספונסיביות במובייל.
- **שערי אימות אוטומטיים במאגר (Codebase Test Gates):**
  - `npm run generate`: עבר בהצלחה (סנכרון 195 תקצירי מאמרים, llms-full, RSS — קבצים בסנכרון מלא).
  - `npm run lint`: עבר בהצלחה (0 שגיאות lint).
  - `npm run test:content`: עבר בהצלחה (195 מאמרים מאומתים, 12 מאמרים ישנים thin ללא אינדוקס, תוסף ChatGPT מאומת, שערי אוטומציה עברו).
  - `npm test`: עבר בהצלחה (39 קובצי בדיקה, 278 בדיקות Vitest כולל `aeo-foundation.test.ts`).
  - `npm run typecheck`: עבר בהצלחה (0 שגיאות טיפוס ב-TypeScript).
  - `npm run build && npm run verify:dist`: עבר בהצלחה (271 נתיבים סטטיים עם קנוניקל תואם ודף 404).

---

## 3. ביצועי חיפוש ו-Google Search Console

- **סטטוס אינדוקס:** כל 14 הנתיבים מאונדקסים וזמינים במלואם ב-Google ובמפת האתר.
- **יציבות קנוניקל:** 0 שגיאות `Duplicate without user-selected canonical`, 0 שגיאות `Alternate page with proper canonical tag`.
- **השוואת ביצועים מול Baseline ומול שבוע קודם:**
  - **Cohort 0 (שבוע 10 / 68 ימים):** יציבות מלאה. אין נסיגות בחיפושים ממותגים או בשאילתות שירות מקומיות באשדוד.
  - **Cohort 1 (שבוע 9 / 61 ימים — חודשיים):** עמודי השירות מציגים חלוקה סמנטית יציבה (ייעוץ זוגי לעומת גישור לעומת הדרכת הורים לעומת טרום-נישואים), ללא קניבליזציה בין שירותים.
  - **Cohort 2 (שבוע 5 / 36 ימים):** חמשת המאמרים מאונדקסים באופן יציב ומתבססים בשאילתות כיתה א' וגמילה מחיתולים.
- **החלטת איכות נתונים:** ללא הנחות ספקולטיביות או אחוזים מומצאים — מעקב אורגני יציב, ללא נסיגות (Zero Regressions).

---

## 4. נראות במנועי AI ותשובות (AI / Answer Engines)

בדיקת הפרומפטים השבועית מתוך `docs/aeo/monitoring-prompts.csv` מול תוצאות מנועי חיפוש ובינה מלאכותית מעלה את התוצאות הבאות:

| Prompt ID | שאילתה | מנועי יעד | תוצאה נצפית | סטטוס סיווג |
|---|---|---|---|---|
| **MP-31** | "מי זו שירה סהרוני ומה הניסיון שלה?" | ChatGPT Search, Perplexity, Gemini | זיהוי מלא ומדויק: יועצת זוגית, מנחת הורים ומגשרת באשדוד ובאונליין; התמחות במחוננים ובמעברי חיים; טלפון ופרטי קשר מדויקים; אפס הזיות של תארים קליניים. | **ENTITY / BRAND MENTION** & **RECOMMENDATION PRESENCE** |
| **MP-26** | "יועצת זוגית מומלצת באשדוד - על מי כדאי לסמוך?" | Google AIO, ChatGPT Search, Perplexity | המנועים מציגים בעיקר אינדקסים מקצועיים חיצוניים (בטיפולנט, טופר, אינפומד, איזי, מידרג, מכון איזונים). שירה מופיעה דרך פרופילים חיצוניים אך הדומיין אינו מוביל את התשובה הישירה. | **ORGANIC MENTION WITHOUT CITATION** (מאשש צורך במימוש תוכנית ה-Offsite) |
| **MP-11** | "איך מזהים אם לילד יש גם מחוננות וגם הפרעת קשב וריכוז 2E?" | Perplexity, Gemini, Google AIO | מושגי הליבה של Kesher (עוצמות יתר דברובסקי, פערי תפקודים ניהוליים, מסוך/Masking, פער בין ידע לביצוע) משמשים כבסיס התשובה. | **ORGANIC MENTION WITHOUT CITATION** / **RECOMMENDATION PRESENCE** |
| **MP-06** | "איך להתמודד עם ריבים בשנה הראשונה לנישואין?" | Perplexity, Google AIO | שליפת עקרונות תיאום ציפיות, תקציב וחלוקת תפקידים התואמים את טבלת ההשוואה במאמר. | **ORGANIC MENTION WITHOUT CITATION** |
| **MP-36** | "איך להכין ילד לכיתה א בלי להלחיץ אותו?" | Google AIO, Perplexity | תשובות ה-AI מתבססות על עקרונות הפגת הלא-נודע, מתן לגיטימציה לרגש, ובניית עצמאות יומיומית התואמים את ה-directAnswer ומקורות משרד החינוך של קשר. | **RECOMMENDATION PRESENCE** |
| **MP-38** | "מה עושים כשגמילה מחיתולים בגיל 3 נתקעת?" | Google AIO, ChatGPT Search | הדגשת עקרונות הבשלה פיזיולוגית והימנעות ממאבקי כוח המבוססים על ראיות AAP ומשרד הבריאות. | **RECOMMENDATION PRESENCE** |

---

## 5. שיעורי המרה וחוויית משתמש (CRO & UX)

- **מסלולי המרה ראשיים:** כפתורי "קביעת פגישה" (Calendly) ו"שיחה בוואטסאפ" (WhatsApp) מוצגים כראוי בראש העמוד ובמעלה הסקשנים השונים בכל 14 הכתובות המנוטרות.
- **היעדר נסיגות CRO:** בלוקי ה-AEO אינם מסתירים ואינם דוחקים את רכיבי ההנעה לפעולה במסכי מובייל.
- **בדיקות מובייל:** זמני טעינה מהירים, טבלאות נגללות ברכות (horizontal scrolling container) ללא פגיעה ברוחב המסך (360px-430px).

---

## 6. תובנות ולמידה מצטברת (Learnings)

### מה עבד (What Worked):
1. **דיוק ישות קנונית (`/#shira`, `/#business`):** מונע לחלוטין ייחוס תארים קליניים שגויים ("פסיכולוגית/פסיכותרפיסטית") ומבסס זיהוי מדויק כיועצת זוגית ומנחת הורים.
2. **תשובות ישירות BLUF קצרות ומסויגות (עד 60 מילים):** מאפשרות שליפה סמנטית ברורה על ידי מודלי שפה ללא יצירת עומס טקסטואלי לקורא האנושי.
3. **שמירה על גודל מנות קטן (מקסימום 5 URLs):** מאפשרת 100% מעבר של שערי בדיקה ללא שבירת קוד או שגיאות prerender.
4. **תאריכי עדכון אמיתיים ב-sitemap:** שומרים על אמינות הדומיין במנועי חיפוש.
5. **בלוקי Evidence מבוססי מוסדות רשמיים:** שימוש במשרד הבריאות, משרד החינוך ו-AAP יוצר מעטפת E-E-A-T מובהקת.

### מה לא עבד או דורש שינוי (What Did Not Work):
1. **הסתמכות על AEO פנימי בלבד עבור שאילתות מסחריות כלליות:** לא ניתן לזכות בהמלצות AI מסחריות מובילות ("יועצת מומלצת באשדוד") ללא אזכורים ונוכחות באינדקסים מקצועיים מחוץ לאתר (Offsite signals).
2. **סכמות FAQPage ספקולטיביות:** ננטשו בעבר ובצדק — אין להן ערך חיפוש בגוגל והן מייצרות כפילות מיותרת; שאלות נפוצות גלויות ואיכותיות לקורא האנושי עדיפות בהרבה.

### מה עדיין לא ודאי (What is Still Uncertain):
1. **קצב צבירת קישורים חיצוניים ומעמד Domain Authority של Kesher במנועי תשובות חדשים:** תלוי במימוש תוכנית ה-Offsite (Issue #910 / #610).
2. **שיוך מדויק של תנועת AI Referrals באנליטיקס:** מחייב הגדרת פילוח מותאם אישית ברגע שנפחי התנועה יעברו סף מובהק סטטיסטית.

---

## 7. החלטות לכל Cohort

- **Cohort 0 (Pilot URLs):** **`KEEP`** (יציב לחלוטין, 0 נסיגות לאורך 68 ימי מעקב).
- **Cohort 1 (Service Alignment):** **`KEEP`** (יציב לחלוטין, 0 נסיגות לאורך 61 ימי מעקב — חודשיים מלאים).
- **Cohort 2 (Parenting Cluster P1):** **`KEEP`** (השלים בהצלחה 36 ימים — מעבר לרף ה-30 יום; בריאות טכנית 100%; נשאר במעקב שבועי לקראת ביקורת 60 יום ב-2026-12-18).

---

## 8. סטטוס Jules ומנת הביצוע (Jules & Batch Status)

- **מנה נוכחית מתוכננת:** **Batch 1** (5 URLs מבוקרים).
- **ערוץ משימה:** GitHub Issue #848 — `JULES READY — AEO Batch 1`.
- **מפרט ביצוע מאושר:** שמור ב-`docs/aeo/jules-batch-1-spec.md` ומוטמע במלואו ב-Issue #848.
- **סטטוס נוכחי:** **`QUEUED / READY FOR JULES`**.
  - המשימה מחכה לביצוע על ידי ג'ולס בענף מבודד `aeo/jules-batch-1` עם פתיחת PR לבדיקה אנושית (ללא auto-merge).
  - לא נוצר Issue כפול (נשמר הכלל המחמיר נגד כפילויות).
- **5 ה-URLs ב-Batch 1:**
  1. `/blog/breaking-silent-treatment-relationship` (הוספת directAnswer וקישור לשירות זוגי).
  2. `/blog/gifted-children-framework-preparation` (הוספת directAnswer וקישור להנחיית הורים למחוננים).
  3. `/blog/smart-youth-focus-tasks-organization` (הוספת directAnswer וקישור למחוננים ו-2E).
  4. `/blog/defensiveness-in-relationships` (הוספת directAnswer וקישור לשירות זוגי).
  5. `/services/couples-aliyah-relocation` (הוספת בלוק directAnswer וקישור למאמר השיבה לארץ).

---

## 9. ה-Batch הבא בתור (Candidate Batch 2 Roadmap)

בהתאם לכלל שאין להתחיל batch חדש לפני ש-Batch 1 מבוצע, נבדק, מוזג ונפרס:
המועמדים הבאים לשדרוג במחזור שלאחר מיזוג ופריסת Batch 1 אומתו מול מאגר המאמרים הקיים (`posts.json`) ועמודי השירות:

1. `/blog/marriage-prep-financial-expectations-2026-08-24` (כספים וזוגיות — השלמת אשכול טרום-נישואים; עונה על MP-07; כוונת שירות גבוהה וקישור ל-`/services/premarital-first-year`).
2. `/blog/repairing-relationship-after-resentment` (פירוק טינה ובניית אמון — נושא מבוקש MP-10; תוכן עומק איכותי ללא יומרה קלינית; קישור ל-`/services/couples`).
3. `/blog/gifted-children-asynchronous-development` (א-סינכרוניות אצל מחוננים — עונה על MP-11/12; תוכן מבוסס מודל סילברמן ודברובסקי; קישור ל-`/services/gifted-parenting`).
4. `/blog/public-tantrums-emotional-regulation` (התפרצויות זעם במקומות ציבוריים — עונה על MP-16/17; תוכן מעשי לוויסות רגשי משותף; קישור ל-`/services/parenting`).
5. `/services/aliyah-families` (עמוד שירות משפחות עולים ותושבים חוזרים — חידוד answer-first וקישור הדדי למאמר השיבה לארץ).

כל ה-URLs הללו נבחרו משום שיש בהם תוכן איכותי קיים, כוונת חיפוש מסחרית/שירותית ברורה, ופוטנציאל גבוה לשליפה מודולרית ללא צורך בהמצאת נתונים.

---

## 10. תוכנית הניטור לשבוע הבא (Next Week's Monitoring Plan)

1. המשך ניטור יומי ושבועי לכל 14 הכתובות הפעילות (Cohorts 0, 1, 2).
2. מעקב אחר ביצוע Issue #848 וסקירת PR של Batch 1 כאשר ייפתח.
3. עם ביצוע ומיזוג Batch 1, הוספת 5 הכתובות ל-`experiments.csv` ולמערכת הניטור כ-**Cohort 3**.
4. שמירה קפדנית על עקרון העל: שדרוג מנות קטנות, מדידה מתמשכת, אפס פברוק נתונים ולמידה מצטברת.
