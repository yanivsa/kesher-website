# KESHER — ChatGPT Remote Publishing Runbook

מדריך להפעלת בקשות פרסום מבוקרות של KESHER מתוך ChatGPT, בלי מחשב מקומי. יצירת מועמד מאמר בענן מאומתת; פרסום מלא של מאמר + NotebookLM Overview + Short עדיין דורש אימות וסמכות נפרדים.

**חשוב — מצב בטיחות נוכחי (22.11.2026):** הפעולות `run_now` ו־`daily` במצב פרסום יוצרות *מועמד פרסום בענף GitHub ו־Pull Request בלבד*. הן אינן מבצעות Merge, Deploy או הפקת סרטונים; החזרת `candidate_pr_pending_ci_and_authority` אינה השלמת שלישייה. יש להמשיך לפרסום רק במסלול בעל סמכות Schema 6 או בגשר מאושר לאחר מעבר בדיקות התוכן, המקור, התמונה ו־CI. לעולם אין לפרסם באמצעות דחיפה ישירה ל־`main` מן המחולל. ה־`resume` הקיים אינו תחליף לאישור פרסום של PR חדש.

**סטטוס מערכת:** **Production E2E Verified: YES (23.11.2026)** — תהליך הפרסום המלא מקצה לקצה הושלם ואומת בייצור (Issue #1442 נסגר). פרסום מאמר, תמונת Hero צילומית ב-16:9, סרטון NotebookLM ארוך ב-16:9, שורט Native ב-9:16, פריסה ל-Cloudflare Pages, ואימות שלישיית הנכסים הציבורית פועלים ומאומתים באופן מלא ועצמאי בענן.

---

## 1. נקודת הכניסה הקנונית (Canonical Entrypoint)

כל פעולות הפרסום, הבדיקה וההתאוששות מנוהלות באופן בלעדי דרך ממשק GitHub Actions:

- **Repository:** `yanivsa/kesher-website`
- **Workflow File:** `.github/workflows/kesher-publish-request.yml`
- **Workflow Name:** `Kesher Publish Request`
- **Workflow ID (Registration):** `426278061`
- **Target Branch:** `main`
- **Endpoint URL:** `https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/dispatches`

---

## 2. הרשאות וממשקי API

### הרשאות נדרשות
- **GitHub Personal Access Token (PAT) / Actions Token** עם הרשאות:
  - `actions: write` (להפעלת dispatches ומעקב אחרי ריצות)
  - `contents: write` (לעדכון קבצים ומצב המאגר)
  - `pull-requests: write`
- הריצות מתבצעות על גבי ענן GitHub Actions המחובר באופן מאובטח ל־Cloudflare Pages, YouTube API ו־NotebookLM באמצעות Secrets המוגדרים במאגר.
- **אין לחשוף סודות או מפתחות בשיחה או במסמכים.**

---

## 3. הפרמטרים המורשים (Workflow Inputs)

| שם פרמטר | סוג | חובה? | ערכי ברירת מחדל / אפשרויות | תיאור |
| :--- | :--- | :--- | :--- | :--- |
| `action` | Choice | **כן** | `daily`, `run_now`, `resume`, `audit`, `repair` | הפעולה המבוקשת לביצוע |
| `slot` | String | לא | ריק (ברירת מחדל: היום לפי שעון ישראל) | תאריך פרסום בפורמט `YYYY-MM-DD` |
| `topic_brief` | String | לא | ריק | הנחיה או נושא מותאם אישית למאמר (מוביל יצירה דינמית) |
| `idea_id` | String | לא | ריק | מזהה ייחודי למאמר (slug באנגלית, lowercase ומקפים) |
| `primary_keyword`| String | לא | ריק | ביטוי מפתח ראשי ייחודי בעברית (SEO) |
| `article_json` | String | לא | ריק | אופציונלי: מחרוזת JSON מלאה של מאמר מוכן לקליטה ישירה |
| `dry_run` | Boolean| לא | `false` | הרצת בדיקה ללא שינוי קבצים, ללא פריסה וללא יצירת וידאו |

---

## 4. דוגמאות קריאות API להפעלה (cURL / GitHub REST API)

### א. הכנת מועמד יומי מבוקר (`daily`)
בודק האם לשלישיית היום יש פרסום מאומת. אם חסר תוכן חדש, יוצר מועמד בענף וב־PR בלבד. אם קיים מאמר לא שלם, לא ייצור כפילות. אין כאן הרשאת פרסום אוטומטי:
```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/dispatches \
  -d '{"ref":"main","inputs":{"action":"daily"}}'
```

### ב. יצירת מועמד תוכן חדש (`run_now`) עם בריף מותאם
מכין PR ואימות CI ראשוני. אינו מפרסם ישירות לאתר, אינו מפיק וידאו או שורט:
```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/dispatches \
  -d '{
    "ref": "main",
    "inputs": {
      "action": "run_now",
      "topic_brief": "איך לעזור לילד שמתקשה להיפרד בבוקר בכניסה לגן בלי בכי ותסכול",
      "primary_keyword": "פרידה בבוקר בגן",
      "idea_id": "morning-separation-daycare-tears"
    }
  }'
```

### ג. הרצת בדיקה יבשה ללא השפעה (`dry_run: true`)
בודק את המאמר, הניקוד, כותרת, תמונת Hero ושלמות הנתונים בלי לבצע Push, בלי לפרוס ובלי ליצור סרטונים:
```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/dispatches \
  -d '{
    "ref": "main",
    "inputs": {
      "action": "run_now",
      "topic_brief": "התמודדות עם שחיקה הורית וחלוקת עומס הוגנת בין בני הזוג",
      "dry_run": true
    }
  }'
```

### ד. בדיקת סטטוס ואימות חוזה ללא שינויים (`audit`)
מריץ את `kesher_cloud_supervisor.py` ומחזיר דוח מקיף על כל הנכסים של היום:
```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/dispatches \
  -d '{"ref":"main","inputs":{"action":"audit"}}'
```

### ה. המשך מחזור שנעצר (`resume`)
מזהה נכסים חסרים (כגון שורט שלא הושלם או וידאו בהמתנה) ומפעיל את השלב המדויק להשלמת השלישייה:
```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/dispatches \
  -d '{"ref":"main","inputs":{"action":"resume"}}'
```

### ו. תיקון ממוקד ומורשה (`repair`)
מפעיל את `scripts.kesher_controller_repair` לסנכרון מצב הבקר ושחרור חסימות:
```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/dispatches \
  -d '{"ref":"main","inputs":{"action":"repair"}}'
```

---

## 5. כיצד לזהות את מזהה הריצה (Run ID) ולעקוב אחרי ההתקדמות

מיד לאחר שליחת ה־POST, המתן 5-10 שניות וקרא את רשימת הריצות האחרונות (מפולטרות לפי `event=workflow_dispatch`):
```bash
curl -s \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/runs?event=workflow_dispatch&per_page=1" \
  | jq '.workflow_runs[0] | {id: .id, status: .status, conclusion: .conclusion, html_url: .html_url, created_at: .created_at}'
```

מעקב אחרי מצב הריצה עד לסיום (`status: "completed"`):
```bash
curl -s \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/yanivsa/kesher-website/actions/runs/<RUN_ID>" \
  | jq '{status: .status, conclusion: .conclusion}'
```

---

## 6. תקני איכות מחייבים למאמר ולתמונה

1. **תמונת Hero צילומית בלבד (Editorial Photography Standard):**
   - יחס 16:9 מדויק (1200x675).
   - צילום מציאותי ועריכתי בלבד (ללא איורים, ללא ציורי Pillow גאומטריים, ללא טקסט על גבי התמונה).
   - גודל קובץ מעל 15KB.
   - גיבוב פיקסלים (SHA-256) ייחודי בכל מאמר למניעת התנגשות בבדיקת `validate-article-images.py`.
   - טקסט אלטרנטיבי (`imageAlt`) בעברית תיאורית מעל 20 תווים.

2. **איכות תוכן ופרסום:**
   - לפחות 500 מילים ו־5 פסקאות עם כותרות `<h3>`.
   - קולה החם, המקצועי והאמפתי של שירה סהרוני.
   - **0 אותיות לטיניות בתוכן הגלוי** (פרט לקישורים ומראי מקום אקדמיים).
   - ציטוטים מדעיים אמיתיים בלבד (PubMed) עם קישור תקין `https://pubmed.ncbi.nlm.nih.gov/...`.
   - קישורים פנימיים למאמרים קיימים בבלוג ולדפי השירותים (`/services/parenting` או `/services/couples`).
   - כותרת מושכת בפורמט שאלה / בעיית קורא (Search-First Clickable Title).

---

## 7. קריאת תוצאות האימות (QA Results & Links)

בסיום הריצה, הקובץ `kesher-publish-result.json` מועלה כ־Artifact בריצה. ניתן גם לקרוא את פלט הלוג ישירות.

מבנה התוצאה:
```json
{
  "action": "run_now",
  "slot": "2026-11-21",
  "slug": "morning-separation-daycare-tears",
  "title": "איך להתמודד עם פרידה בבוקר בגן? מדריך מעשי לחיזוק הקשר",
  "article_url": "https://kesher.saharoni.com/blog/morning-separation-daycare-tears",
  "source_sha256": "...",
  "contract_complete": true,
  "status": "success"
}
```

---

## 8. פעולות אסורות (Strict Safety Gates)

1. **איסור עקיפת בקר התוכן:** אין ליצור בקר מתחרה או לעקוף את מנגנון Schema 6.
2. **איסור כתיבה כפולה:** אין לפרסם מאמר עם slug או מזהה שכבר קיימים ב־`posts.json` או `postsRecent.json`.
3. **איסור דיווח הצלחה שווא:** `Contract Complete: YES` מוחזר אך ורק כאשר שלושת הנכסים אומתו במלואם ב־`kesher_cloud_supervisor.py`.
4. **איסור הפעלת Workflows שהושבתו במכוון:** כגון מסלול Jules הישן ב־`kesher-article-generation.yml` שהוצא משימוש.
5. **איסור אותיות לטיניות בתוכן הגלוי:** כל גוף המאמר חייב להיות בעברית שוטפת וטבעית.

### הפעלה יומית ב־01:00 שעון ישראל (שעון קיץ/חורף)

בקשת הפרסום הקנונית `.github/workflows/kesher-publish-request.yml` כוללת כעת `on.schedule` עם `cron: "0 1 * * *"` ו־`timezone: "Asia/Jerusalem"`. זו תכונה מובנית של GitHub Actions; אין צורך בשתי הפעלות UTC שייצרו טריגר נוסף בכל יום.

הפעלת לוח הזמנים עוברת **רק** דרך פעולת `daily` הקיימת. לפני הפעלת המחולל יש שער קריאה בלבד שחוסם כניסה נוספת אם יש מחזור פרסום `queued/in_progress` או PR מועמד פתוח לאותו יום ישראלי. כשל בקריאת GitHub חוסם את הפעולה; אין מעקף של Schema-6, CI או אישור מיזוג. מנגנון `daily` בודק אם כבר קיים מאמר וחוזר להשלמת המדיה במקום לייצר מאמר כפול. ריצות יזומות ו־IssueOps אינן משתנות.

**חשוב:** תזמון ב־01:00 אינו התחייבות לדיוק של שנייה; GitHub עשוי לעכב התחלת Scheduled Actions. גם לאחר שיגור `daily`, כל שלושת הנכסים מחויבים לעבור את שערי האישור וה־Receipt לפני שניתן להכריז על השלמת המחזור.
