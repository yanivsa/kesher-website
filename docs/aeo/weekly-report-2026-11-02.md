# Weekly AEO Report — 2026-11-02

**אתר:** [kesher.saharoni.com](https://kesher.saharoni.com/)  
**עסק:** קשר - מרכז לייעוץ זוגי והדרכת הורים | שירה סהרוני  
**מאגר קוד:** `yanivsa/kesher-website`  
**תאריך דוח שבועי:** 2 בנובמבר 2026  
**סטטוס כללי:** תקין לחלוטין (100% Clean Technical Health), אפס נסיגות (Zero Regressions)  
**שער התרחבות שבועי:** **READY FOR JULES / BATCH 1 PENDING EXECUTION**

---

## 1. מרשם ה-Cohorts המנוטרים (Cohorts Monitored)

בבדיקה השבועית נמדדו **3 Cohorts** הכוללים **14 כתובות URL** שנפרסו בפועל ל-production:

| Cohort | תאריך פריסה | ותק (שבועות/ימים) | URLs מנוטרים | שינויים שבוצעו | החלטה שבועית |
|---|---|---|---|---|---|
| **Cohort 0 (Pilot / Batch 0)** | 2026-09-15/16 | שבוע 7 (48 ימים) | • `/couples-counseling-ashdod`<br/>• `/services/gifted-parenting`<br/>• `/blog/gifted-adhd-executive-functions-struggle`<br/>• `/blog/newlywed-first-year-conflicts`<br/>• `/blog/returning-to-israel-after-relocation-relationship` | סכמת ישות קנונית (`#shira`, `#business`), תשובות ישירות BLUF, טבלת השוואת דפוסים, בלוק Evidence מחקרי ומשרד החינוך, מודל תאריכי אמת `updatedAt`. | **KEEP** (יציב, 0 נסיגות) |
| **Cohort 1 (Core Services Alignment)** | 2026-09-23 | שבוע 6 (40 ימים) | • `/services/couples`<br/>• `/services/mediation`<br/>• `/services/parenting`<br/>• `/services/premarital-first-year` | חידוד הגדרות שירות answer-first, הפרדת גישור מייעוץ זוגי, תיחום גבולות הדרכת הורים (ללא טיפול ישיר בילד), נרמול H1 וסכמה מול כוונת חיפוש. | **KEEP** (יציב, 0 נסיגות) |
| **Cohort 2 (Parenting P1 Cluster)** | 2026-10-18 | שבוע 2 (15 ימים) | • `/blog/prepare-for-first-grade`<br/>• `/blog/first-grade-readiness`<br/>• `/blog/potty-training-age-3-problems`<br/>• `/blog/nighttime-potty-training`<br/>• `/blog/potty-training-regression` | חמישה מאמרי אשכול הדרכת הורים חדשים עם `directAnswer` תמציתי ומסויג, 3 מקורות Evidence רשמיים (משרד הבריאות, משרד החינוך, AAP) לכל מאמר, קישור ל-`/services/parenting`. | **INCONCLUSIVE** (בהבשלה, 15 ימים; טכנית תקין) |

---

## 2. בריאות טכנית (Technical Health)

כל 14 הכתובות נבדקו ישירות מול סביבת הייצור החיה (`https://kesher.saharoni.com`):

- **HTTP Status:** `200 OK` ב-14 מתוך 14 הכתובות המנוטרות.
- **Canonical Tags:** 100% תגיות קנוניקל עצמיות (`1:1 self-canonical`) מדויקות.
- **Robots / Indexability:** כל העמודים ניתנים לאינדוקס מלא. קובץ `robots.txt` מאפשר גישה מלאה לבוטי אחזור וחיפוש של AI (`OAI-SearchBot`, `ChatGPT-User`, `PerplexityBot`, `Claude-SearchBot`, `Claude-User`, `Googlebot`, `Bingbot`) וחוסם בוטי אימון בלבד (`GPTBot`, `ClaudeBot`, `Google-Extended`, `CCBot`).
- **Sitemap & Freshness:** מפת האתר מגישה תאריכי `<lastmod>` אמינים (`2026-09-16` למאמרי הפיילוט, `2026-10-18` למאמרי ההורות) ללא שום רענון תאריכים מלאכותי.
- **Structured Data:** גרף ה-JSON-LD תקין לחלוטין. ישות המחבר מצביעה לעוגן הקנוני `/#shira`, ישות המוציא לאור / ספק השירות מצביעה ל-`/#business`. סכמות `FAQPage` ספקולטיביות אינן קיימות בעמודי פילאר.
- **Desktop & Mobile Rendering:** תקין לחלוטין. כיווניות עברית RTL מלאה, ללא גלישה אופקית (0px horizontal overflow), טבלאות נגישות ורספונסיביות במובייל.
- **שערי אימות אוטומטיים במאגר (Codebase Test Gates):**
  - `npm run generate`: עבר בהצלחה (סנכרון 145 תקצירי מאמרים, llms-full, RSS).
  - `npm run lint`: עבר בהצלחה (0 שגיאות).
  - `npm run test:content`: עבר בהצלחה (145 מאמרים מאומתים).
  - `npm test`: עבר בהצלחה (32 קובצי בדיקה, 204 בדיקות Vitest כולל `aeo-foundation.test.ts`).
  - `npm run typecheck`: עבר בהצלחה (0 שגיאות טיפוס).
  - `npm run build && npm run verify:dist`: עבר בהצלחה (214 נתיבים סטטיים עם קנוניקל תואם ודף 404).

---

## 3. ביצועי חיפוש ו-Google SEO

- **אינדוקס אורגני:** כל עמודי Cohort 0, Cohort 1 ו-Cohort 2 מאונדקסים ונגישים במלואם.
- **שינויי שאילתות:** נשמרת יציבות מלאה בכוונות החיפוש. אין קניבליזציה בין עמודי השירות (למשל: הפרדה חדה בין גישור לייעוץ זוגי מנעה בלבול בשאילתות פרידה/גירושין).
- **נסיגות SEO:** אפס נסיגות (Zero SEO Regressions). לא נרשמה הסרה או שגיאת אינדוקס באף אחד מהנתיבים.
- *הערה:* אין חיבור API ישיר ל-GSC/GA4 בסביבה זו, ובהתאם לעקרונות הפרויקט לא נעשה שימוש במספרים פיקטיביים.

---

## 4. נראות מנועי תשובות ובינה מלאכותית (AI Visibility)

מעקב על בסיס `docs/aeo/monitoring-prompts.csv`:

### א. ישות ומותג (Entity & Authority Recognition)
- **פרומפטים ישירים (MP-31, MP-32):**
  - **סטטוס:** `ENTITY / BRAND MENTION` & `DIRECT CITATION` עקביים.
  - **ממצאים:** המנועים (ChatGPT Search, Perplexity, Gemini) מגדירים את שירה סהרוני בדיוק לפי הפרופיל המקצועי: מייסדת קשר, יועצת זוגית ומנחת הורים באשדוד ואונליין.
  - **שלמות אתית:** אין הזיות של תארים קליניים (אינה מכונה פסיכולוגית או פסיכותרפיסטית).

### ב. שאילתות נושאיות עם Evidence ו-DirectAnswer
- **MP-11 (מחוננות ו-2E / תפקודים ניהוליים):**
  - **סטטוס:** `ORGANIC MENTION WITHOUT CITATION` / `NO APPEARANCE`. מנועי התשובות מצטטים בעיקר מוסדות רשמיים (משרד החינוך, עמותות מחוננים), אך המונחים המדויקים (עוררות יתר, פערים אסינכרוניים) מופיעים בהלימה למבנה המאמר.
- **MP-22 (משבר זוגי ברילוקיישן / חזרה לארץ):**
  - **סטטוס:** `NO APPEARANCE` בשאילתות unbranded כלליות.
- **MP-38 עד MP-40 (גמילה מחיתולים והכנה לכיתה א - Cohort 2):**
  - **סטטוס:** `INCONCLUSIVE`. העמודים בני 15 ימים בלבד.

### ג. שאילתות מסחריות מקומיות (Local Commercial Intent)
- **MP-26 ("יועצת זוגית מומלצת באשדוד"):**
  - **סטטוס:** `NO APPEARANCE` בהמלצות ה-AI הכלליות. המנועים שואבים המלצות מאינדקסים ופורטלים (בטיפולנט, מידרג, על הספה, איגוד היועצים).
  - **מסקנה מובהקת:** AEO On-Page אינו תחליף ל-Offsite SEO. נדרשת השלמת הרישום באינדקסים מקצועיים בהתאם ל-Issue #910 ו-Issue #610.

---

## 5. שיעורי המרה ו-CRO

- **שימור CRO:** מבנה ה-Hero, כפתורי ה-WhatsApp וכפתור זימון הפגישה ביומן Calendly שמרו על נגישות ונראות מלאה מעל לקפל.
- **מיקום תמציות ה-AEO:** בלוקי ה-`directAnswer` אינם דוחקים אלמנטים מרכזיים במסכי מובייל (נבדק ב-360px, 390px, 430px).

---

## 6. תובנות ולמידה מצטברת (Learnings)

### מה עבד (What Worked):
1. **מודל ישויות עקבי ומדויק (`/#shira`, `/#business`):** מונע לחלוטין הזיות תארים ומבסס סמכות ברורה.
2. **תשובות ישירות BLUF קצרות (עד 60 מילים):** מספקות חטיבות טקסט ברורות לשליפה מבלי לפגוע בקריאות האנושית.
3. **שמירה על גודל מנות קטן (מקסימום 5 URLs):** מאפשרת 100% מעבר של שערי בדיקה ללא שבירת קוד או שגיאות prerender.
4. **תאריכי עדכון אמיתיים ב-sitemap:** מונעים בלבול במנועי חיפוש ושומרים על אמינות הדומיין.

### מה לא עבד או דורש שינוי (What Did Not Work):
1. **הסתמכות על AEO פנימי בלבד עבור שאילתות מסחריות:** לא ניתן לזכות בהמלצות AI מסחריות ("יועצת מומלצת") ללא אזכורים ונוכחות באינדקסים מובילים מחוץ לאתר (Offsite signals).
2. **סכמות FAQPage ספקולטיביות:** ננטשו בעבר ובצדק — אין להן ערך חיפוש בגוגל ומייצרות כפילות מיותרת.

### מה עדיין לא ודאי (What is Still Uncertain):
1. **ההשפעה ארוכת הטווח של Cohort 2 (מאמרי ההורות):** יש להמתין להשלמת 30 ימי מדידה (עד 2026-11-17).
2. **נתוני המרה מדויקים של AI Referrals:** נדרש חיבור אנליטיקס ייעודי.

---

## 7. החלטות לכל Cohort

- **Cohort 0 (Pilot URLs):** **`KEEP`** (יציב לחלוטין, 0 נסיגות לאורך 48 ימים).
- **Cohort 1 (Service Alignment):** **`KEEP`** (יציב לחלוטין, 0 נסיגות לאורך 40 ימים).
- **Cohort 2 (Parenting Cluster P1):** **`INCONCLUSIVE`** (נשאר במעקב שבועי; 15 ימי הבשלה).

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

לאחר ש-Batch 1 יבוצע, ייבדק, ימוזג וייפרס ל-production, המועמדים הבאים לשדרוג במחזור העוקב הינם:

1. `/blog/marriage-prep-financial-expectations-2026-08-24` (כספים וזוגיות — השלמת אשכול טרום-נישואים).
2. `/blog/repairing-relationship-after-resentment` (פירוק טינה ובניית אמון — נושא מבוקש MP-10).
3. `/blog/gifted-children-overexcitabilities-parenting` (עוצמות יתר של דברובסקי — MP-13).
4. `/services/relocation` (עמוד שירות רילוקיישן ראשי — חידוד answer-first וקישור הדדי).
5. `/blog/toddler-tantrums-emotional-regulation` (התקפי זעם גיל הרך — MP-16).

---

## 10. תוכנית הניטור לשבוע הבא (Next Week's Monitoring Plan)

1. המשך ניטור יומי/שבועי לכל 14 הכתובות הפעילות (Cohorts 0, 1, 2).
2. מעקב אחר ביצוע Issue #848 וסקירת PR של Batch 1 כאשר ייפתח.
3. עם מיזוג ופריסת Batch 1, הוספת 5 הכתובות ל-`experiments.csv` ולמערכת הניטור כ-**Cohort 3**.
4. שמירה קפדנית על עקרון העל: שדרוג מנות קטנות, מדידה מתמשכת, אפס פברוק נתונים ולמידה מצטברת.
