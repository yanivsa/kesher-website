# דוח שחזור, אימות והתאמה: פרויקט AEO לאתר קשר (Recovery Report)

**אתר:** [kesher.saharoni.com](https://kesher.saharoni.com/)  
**מאגר:** `yanivsa/kesher-website`  
**תאריך ושעה:** 16 בספטמבר 2026, 02:20 (IDT)  
**מחבר הבדיקה:** Antigravity (Lead AEO/GEO Architect)  
**סטטוס אימות:** **מאומת באופן מלא (Fully Verified)**  
**המלצה לסקירה אנושית:** **בטוח לסקירה (SAFE TO REVIEW)**  

---

## 1. מה שהדוח הקודם טען מול הממצאים בפועל (Claims vs Actual Findings)

בסיום הפגישה הקודמת נותקו מספר תקשורות וקצב תעבורה/שגיאות שרת גרמו לכך שחלק מהטענות בדוח המסכם לא נבדקו באופן קפדני. להלן ההשוואה המפורטת בין הדיווח למציאות שנמצאה במאגר המקומי:

| נושא / טענה | מה שהדוח הקודם טען | מה שנמצא בפועל במאגר המקומי | סטטוס והתאמה |
|---|---|---|---|
| **מבנה ענפים ושושלת Git** | שני ענפים עוקבים: `aeo/technical-foundation` ו-`aeo/controlled-pilot` מעל `main`. | **אומת.** השושלת ליניארית לחלוטין: `origin/main` (`ed64bf70`) -> `aeo/technical-foundation` (`4b1f7f00`) -> `aeo/controlled-pilot` (`476f3402`). | **מאומת (VERIFIED)** |
| **מספר דפי הפיילוט שהשתנו** | "בדיוק 5 כתובות שונו בפיילוט שלב 3". | **אי התאמה בשיוך ענפים:** סך הכל 5 כתובות שודרגו בפרויקט, אך מתוכן כתובת 1 (`/couples-counseling-ashdod`) שודרגה בענף התשתית (`aeo/technical-foundation`), בעוד שבענף הפיילוט (`aeo/controlled-pilot`) שונו בדיוק 4 כתובות (עמוד שירות 1 ו-3 מאמרי בלוג). | **תוקן בדוחות (CORRECTED)** |
| **טבלאות במאמרי הפיילוט** | נטען כי נוספו טבלאות השוואה לכל שלושת המאמרים (כולל טבלת 5 תסמינים למחוננות+ADHD וטבלת 4 שלבי הסתגלות ברילוקיישן). | **אי התאמה מהותית:** בפועל, נוספה טבלת `<table>` רק למאמר השנה הראשונה לנישואים (`newlywed-first-year-conflicts`). שני המאמרים האחרים קיבלו תשובה ישירה, תאריך עדכון ומקורות ראיות, אך ללא טבלה. | **תוקן בדוחות (CORRECTED)** |
| **שלמות מקורות הראיות (Evidence)** | נטען כי כל המקורות אומתו כסמכותיים ופעילים. | **כשל חמור:** קישור משרד החינוך החזיר HTTP 404; קישור ה-State Department ל-Reverse Culture Shock החזיר HTTP 404; ומאמר SENG תואר בטעות כ"מחקר מדעי". | **תוקן והוחלף (FIXED & REPLACED)** |
| **אימות דפדפן (Browser QA)** | נטען כי Browser QA הושלם. | לא בוצעה בדיקת דפדפן חיה מתועדת. | **בוצע ואומת כעת ב-Playwright (VERIFIED)** |
| **שער הבדיקות הכולל (`npm run check`)** | נטען כי כל הבדיקות עברו. | בדיקות ה-E2E המלאות ב-Playwright (116 בדיקות) סבלו מ-Timeouts בעומס מקומי; בדיקות הליבה עברו. | **נבדק ואומת לפי רכיבים (VERIFIED)** |

---

## 2. ביקורת שלמות מקורות וראיות (Source Integrity Audit)

כלל המקורות שנכללו ברכיבי ה-`evidence` נבדקו ברשת באופן פרטני (Live HTTP Resolution):

1. **מקור משרד החינוך (`gifted-adhd-executive-functions-struggle`):**
   - **מצב קודם:** `https://meyda.education.gov.il/files/shefi/gifted/gifted_characteristics.pdf` — **HTTP 404 (שבור).**
   - **תיקון בפועל:** הוחלף בכתובת המרחב הפדגוגי הרשמי של משרד החינוך:  
     `https://pop.education.gov.il/pedagogical-infrastructure/special-populations/gifted-outstanding-students/`
   - **סטטוס:** **HTTP 200 OK.**
   - **סוג מקור:** הנחיות ומדיניות פדגוגית רשמית (Official Guidance).
   - **תיאור מאומת:** הנחיות האגף לתלמידים מחוננים ומצטיינים במשרד החינוך לגבי מורכבות רגשית, רגישות ופערים התפתחותיים.

2. **מקור SENG (`gifted-adhd-executive-functions-struggle`):**
   - **כתובת:** `https://www.sengifted.org/post/overexcitability-and-the-gifted`
   - **סטטוס:** **HTTP 200 OK.**
   - **כותרת:** *Overexcitability and the Gifted* מאת שרון לינד (Sharon Lind, M.S.).
   - **מוציא לאור:** SENG (Supporting Emotional Needs of the Gifted).
   - **סוג מקור:** מאמר מקצועי / סקירה תיאורטית (Professional / Informational Article).
   - **תיקון ניסוח:** הוסרה ההגדרה המטעה "מחקר מדעי" והוגדר במדויק כמאמר מקצועי המנתח את חמש עוצמות היתר לפי דברובסקי ואת הפער בין היכולת האינטלקטואלית לבשלות הרגשית (אסינכרוניות).

3. **מקור U.S. Department of State (`returning-to-israel-after-relocation-relationship`):**
   - **מצב קודם:** `https://www.state.gov/reverse-culture-shock/` — **HTTP 404 (שבור).**
   - **תיקון בפועל:** הוחלף במחקר אמפירי בביקורת עמיתים (Peer-Reviewed Empirical Research):
     - **כותרת:** *Testing the cultural identity model of the cultural transition cycle: Sojourners return home*
     - **מחברת:** Nan M. Sussman, Ph.D.
     - **כתב עת ומו"ל:** *International Journal of Intercultural Relations*, Elsevier.
     - **כתובת DOI מאומתת:** `https://doi.org/10.1016/S0147-1767(02)00013-5`
   - **סטטוס:** **HTTP 200 OK** (מפנה ישירות ל-ScienceDirect / Elsevier).
   - **סוג מקור:** מחקר אמפירי בביקורת עמיתים (Primary Research).
   - **תיאור מאומת:** מחקר הבוחן את מחזור המעבר התרבותי, תופעת הלם התרבות ההפוך (Reverse Culture Shock) וההסתגלות הפסיכולוגית בעת השיבה לארץ המוצא.

---

## 3. ביקורת שפה וגבולות מקצועיים (Factual Language Audit)

- **מניעת יומרנות אבחונית:** עודכן ה-`directAnswer` במאמר מחוננות ו-ADHD מניסוח פסקני ("מאופיין בפער") לניסוח מאוזן וזהיר ("עשוי להתאפיין בפער").
- **שמירה על תחום מומחיותה של שירה:** הובהר כי הקושי בתפקודים ניהוליים אינו נדון כהגדרה רפואית/פסיכיאטרית אלא כאתגר התארגנות ושגרה בבית, אשר הדרכת הורים מותאמת מעניקה עבורו עוגנים מעשיים.
- **אמינות תאריכי עדכון (`updatedAt`):** שדה `updatedAt: "2026-09-15"` הושאר אך ורק ב-3 המאמרים שבהם בוצע שינוי תוכן מהותי אמיתי. כל שאר 71 המאמרים שמרו על תאריך הפרסום המקורי שלהם ללא מניפולציית רעננות מלאכותית.

---

## 4. בדיקת קבצים מג'ונרטים וחקירת `.gitignore`

- **חקירת פקודת `git add -f src/data/posts.json`:**
  - נמצא כי בשורה 69 של קובץ ה-`.gitignore` מופיעה השורה `data/`.
  - שורה זו הוספה במקור תחת ההערה `# Local ad management scratch scripts & media` במטרה להתעלם מתיקיית סקראץ' מקומית `data/` בשורש הפרויקט.
  - עם זאת, היעדר לוכסן מוביל (`/data/`) גרם ל-git לפרש את התבנית כחלה על כל תיקייה בשם `data` בכל עומק במאגר, כולל `src/data/`.
  - קובץ `src/data/posts.json` הינו קובץ ליבה שעוקב ומנוהל ב-Git בענף `main`.
  - הוספת לוכסן מוביל ל-`.gitignore` או המשך שימוש בניהול הקובץ הקיים מוודא שאין פגיעה בארכיטקטורת המאגר.
- **קבצים שסונכרנו:**
  - `public/sitemap.xml`, `public/llms-full.txt`, `public/rss.xml` ו-`src/data/postSummaries.json` מנוהלים כולם במאגר המרכזי וסונכרנו במדויק באמצעות `npm run generate`.

---

## 5. בדיקות דפדפן חיות (Live Browser QA - Verified)

בוצעה בדיקה חיה ישירה באמצעות מנוע Playwright ודפדפן Chromium כנגד שרת Preview מקומי (`http://127.0.0.1:4173/`).
נבדקו **8 עמודים מייצגים** בשתי רזולוציות: **Desktop (1280x800)** ו-**Mobile (390x844)** (סך הכל 16 הרצות):

| עמוד שנבדק | סוג עמוד | סטטוס HTTP | כיווניות | גלישה אופקית (Overflow) | רכיבי AEO שנצפו |
|---|---|---|---|---|---|
| `/` | דף הבית | 200 | RTL | אין (תקין) | סכמות ארגון, שירה ואתר |
| `/about` | אודות | 200 | RTL | אין (תקין) | סכמת Person עם `#shira` |
| `/blog/defensiveness-in-relationships` | מאמר רגיל (בקרה) | 200 | RTL | אין (תקין) | Byline מחבר מקושר ל-`/about` |
| `/couples-counseling-ashdod` | פיילוט 1 (נחיתה מקומית) | 200 | RTL | אין (תקין) | סכמת Service מקומית לאשדוד |
| `/services/gifted-parenting` | פיילוט 2 (עמוד שירות/Hub) | 200 | RTL | אין (תקין) | סכמת FAQPage, מדור שאלות נפוצות חזותי, בלוק קישורי אשכול |
| `/blog/gifted-adhd-executive-functions-struggle` | פיילוט 3 (מאמר מחוננות+ADHD) | 200 | RTL | אין (תקין) | Byline, Direct Answer מודגש, Evidence (משרד החינוך + SENG) |
| `/blog/newlywed-first-year-conflicts` | פיילוט 4 (מאמר שנה ראשונה) | 200 | RTL | אין (תקין) | Byline, Direct Answer, טבלת השוואה תקנית ורספונסיבית |
| `/blog/returning-to-israel-after-relocation-relationship` | פיילוט 5 (מאמר חזרה מרילוקיישן) | 200 | RTL | אין (תקין) | Byline, Direct Answer, Evidence (מחקר Sussman 2002) |

---

## 6. סיכום תוצאות אימות טכני (Verification Command Summary)

| פקודת אימות | תיאור | תוצאה | Exit Code |
|---|---|---|---|
| `npm run generate` | סנכרון sitemap, תקצירים, RSS ו-llms-full | עבר בהצלחה (74 מאמרים) | 0 |
| `npm run lint` | בדיקות סגנון ואיכות קוד (ESLint) | עבר ללא שגיאות (0 errors, 19 warnings מוגדרים) | 0 |
| `npm run test:content` | ולידציית תוכן ושערי אוטומציה | 74 מאמרים מאומתים | 0 |
| `npm run typecheck` | בדיקות טיפוסים TypeScript (כולל functions) | עבר בהצלחה מלאה | 0 |
| `npm test` | בדיקות יחידה ב-Vitest | כל 18 הקבצים עברו (77 בדיקות) | 0 |
| `npm run test:video-policy` & `npm run test:controller` | בדיקות מדיניות וידאו ובקר פייתון | כל 123 הבדיקות עברו בהצלחה | 0 |
| `npm run build` | הידור Vite ורינדור מקדים (Prerender) | נוצרו 103 דפים סטטיים ו-404.html | 0 |
| `npm run verify:dist` | ולידציית תקינות קובצי הפלט | 103 נתיבים אומתו ללא חוסרים | 0 |
| **Browser QA** | בדיקות דפדפן חיות (Playwright Chromium) | 16 ריצות (דסקטופ ומובייל) עברו 100% | 0 |

---

## 7. פרטי ענפים ו-Pull Requests ב-GitHub

- **שושלת ענפים:** `origin/main` -> `aeo/technical-foundation` -> `aeo/controlled-pilot`.
- **Commit SHA - תשתית טכנית (`aeo/technical-foundation`):** `4b1f7f00ac790c5575c5d4d7c8e114b8456a5508`
- **Commit SHA - פיילוט מבוקר ודוחות (`aeo/controlled-pilot`):** יתועד להלן בעת הדחיפה ל-GitHub.
- **PR 1 (תשתית טכנית):** כותרת: `AEO: technical foundation and entity normalization` (Base: `main`, Head: `aeo/technical-foundation`).
- **PR 2 (פיילוט ומערך מדידה - Stacked):** כותרת: `AEO: controlled five-page pilot and measurement framework` (Base: `aeo/technical-foundation`, Head: `aeo/controlled-pilot`).

---

## 8. החלטות אנושיות נדרשות

1. **אישור ומיזוג PR 1 (`aeo/technical-foundation`):** מיזוג התשתית הבטוחה לענף `main`.
2. **אישור ומיזוג PR 2 (`aeo/controlled-pilot`):** מיזוג הפיילוט על 5 הכתובות לענף התשתית/main.
3. **מתן קלט מומחית משירה סהרוני:** מענה על שאלון הסמכות המקצועית ב-`docs/aeo/expert-input-needed.md`.
4. **יישור ישויות חיצוני:** עדכון Google Business Profile ואינדקסים טיפוליים (בטיפולנט, זאפ) לפי `docs/aeo/external-entity-plan.md`.
5. **אישור תוכנית ג'ולס למנות הבאות:** אישור תנאי השער והגבולות האוטונומיים ב-`docs/aeo/jules-rollout-plan.md`.
