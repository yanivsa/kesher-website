# KESHER — ChatGPT Remote Publishing Runbook

מדריך הפעלה רשמי ומלא עבור ChatGPT להפעלת מחזור פרסום אוטונומי באתר KESHER (מאמר + וידאו NotebookLM ארוך + שורט) ללא תלות ב־Antigravity וללא צורך במחשב מקומי.

---

## 1. נקודת הכניסה הקנונית (Canonical Entrypoint)

כל פעולות הפרסום, הבדיקה וההתאוששות מנוהלות באופן בלעדי דרך ממשק GitHub Actions:

- **Repository:** `yanivsa/kesher-website`
- **Workflow File:** `.github/workflows/kesher-publish-request.yml`
- **Workflow Name:** `Kesher Publish Request`
- **Target Branch:** `main`
- **Endpoint URL:** `https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/dispatches`

---

## 2. הרשאות וממשקי API

### הרשאות נדרשות
- **GitHub Personal Access Token (PAT) / Actions Token** עם הרשאות:
  - `actions: write` (להפעלת dispatches ומעקב אחרי ריצות)
  - `contents: read` (לקריאת קבצים ומצב המאגר)
- הריצות מתבצעות על גבי ענן GitHub Actions המחובר באופן מאובטח ל־Cloudflare Pages, YouTube API ו־NotebookLM באמצעות Secrets המוגדרים במאגר.
- **אין לחשוף סודות או מפתחות בשיחה או במסמכים.**

---

## 3. הפרמטרים המורשים (Workflow Inputs)

| שם פרמטר | סוג | חובה? | ערכי ברירת מחדל / אפשרויות | תיאור |
| :--- | :--- | :--- | :--- | :--- |
| `action` | Choice | **כן** | `daily`, `run_now`, `resume`, `audit`, `repair` | הפעולה המבוקשת לביצוע |
| `slot` | String | לא | ריק (ברירת מחדל: היום לפי שעון ישראל) | תאריך פרסום בפורמט `YYYY-MM-DD` |
| `topic_brief` | String | לא | ריק | הנחיה או נושא מותאם אישית למאמר |
| `idea_id` | String | לא | ריק | מזהה ייחודי למאמר (slug-like token) |
| `primary_keyword`| String | לא | ריק | ביטוי מפתח ראשי ייחודי בעברית |
| `article_json` | String | לא | ריק | אופציונלי: JSON מלא של המאמר שנכתב ע״י ChatGPT |
| `dry_run` | Boolean| לא | `false` | הרצת בדיקה ללא שינוי קבצים, ללא פריסה וללא יצירת וידאו |

---

## 4. דוגמאות קריאות API להפעלה (cURL / GitHub REST API)

### א. פרסום יומי אוטומטי (`daily`)
בודק האם לשלישיית היום כבר יש פרסום מאומת. אם קיים — מדווח על השלמה ללא כפילות. אם חסר — מפעיל את מלוא מחזור הפרסום (מאמר, תמונה, פריסה, וידאו, שורט ואימות):
```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/dispatches \
  -d '{"ref":"main","inputs":{"action":"daily"}}'
```

### ב. יצירת שלישייה חדשה מיד (`run_now`)
יוצר מאמר נוסף באותו התאריך (או בתאריך מבוקש), תוך הבטחת בידוד מלא ומניעת כפילויות:
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
      "topic_brief": "איך לעזור לילדים להיפרד מפעילות אהובה בלי התפרצויות זעם"
    }
  }'
```

### ג. בדיקת סטטוס ואימות חוזה ללא שינויים (`audit`)
מריץ את `kesher_cloud_supervisor.py` ומחזיר דוח מקיף על כל הנכסים של היום:
```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/dispatches \
  -d '{"ref":"main","inputs":{"action":"audit"}}'
```

### ד. המשך מחזור שנעצר (`resume`)
מזהה נכסים חסרים (כגון שורט שלא הושלם או וידאו בהמתנה) ומפעיל את השלב המדויק להשלמת השלישייה:
```bash
curl -X POST \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/dispatches \
  -d '{"ref":"main","inputs":{"action":"resume"}}'
```

### ה. תיקון ממוקד ומורשה (`repair`)
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

מיד לאחר שליחת ה־POST, המתן 5-10 שניות וקרא את רשימת הריצות האחרונות:
```bash
curl -s \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/kesher-publish-request.yml/runs?per_page=1" \
  | jq '.workflow_runs[0] | {id: .id, status: .status, conclusion: .conclusion, html_url: .html_url}'
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

## 6. קריאת תוצאות האימות (QA Results & Links)

בסיום הריצה, הקובץ `kesher-publish-result.json` מועלה כ־Artifact בריצה. ניתן גם לקרוא את פלט הלוג ישירות.

מבנה התוצאה:
```json
{
  "action": "daily",
  "slot": "2026-11-21",
  "slug": "smooth-transitions-toddler-activities-cooperation",
  "title": "מעברים חלקים בין פעילויות: איך לעזור לילדים להיפרד ממשחק בלי התפרצויות",
  "article_url": "https://kesher.saharoni.com/blog/smooth-transitions-toddler-activities-cooperation",
  "video_url": "https://www.youtube.com/watch?v=XYmhXUSIAaw",
  "short_url": "https://www.youtube.com/shorts/JxkDcDcJV4c",
  "contract_complete": true,
  "status": "success"
}
```

---

## 7. אימות שלושת הקישורים הציבוריים

שלושת הקישורים חייבים לעמוד בתנאי החוזה:
1. **מאמר באתר:**
   `https://kesher.saharoni.com/blog/<SLUG>` — מחזיר HTTP 200, כולל תמונת Hero ביחס 16:9, תוכן עשיר בעברית והטמעת הווידאו.
2. **וידאו ארוך (NotebookLM 16:9):**
   `https://www.youtube.com/watch?v=<VIDEO_ID>` — סרטון Public בערוץ הרשמי, עם קריינות עברית וחתימת שירה סהרוני.
3. **שורט (NotebookLM 9:16):**
   `https://www.youtube.com/shorts/<SHORT_ID>` — שורט אנכי Public בערוץ הרשמי, עם קישור קנוני למאמר בתיאור וחתימת סגיר.

---

## 8. פעולות אסורות (Strict Safety Gates)

1. **איסור עקיפת בקר התוכן:** אין ליצור בקר מתחרה או לעקוף את מנגנון Schema 6.
2. **איסור כתיבה כפולה:** אין לפרסם מאמר עם slug או מזהה שכבר קיימים ב־`posts.json` או `postsRecent.json`.
3. **איסור דיווח הצלחה שווא:** `Contract Complete: YES` מוחזר אך ורק כאשר שלושת הנכסים אומתו במלואם ב־`kesher_cloud_supervisor.py`.
4. **איסור הפעלת Workflows שהושבתו במכוון:** כגון מסלול Jules הישן ב־`kesher-article-generation.yml` שהוצא משימוש.
5. **איסור אותיות לטיניות בתוכן הגלוי:** כל גוף המאמר חייב להיות בעברית שוטפת וטבעית, ללא מונחים באנגלית בסוגריים.
