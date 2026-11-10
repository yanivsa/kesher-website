# JULES READY — AEO Batch 1 Specification

**Branch:** `aeo/jules-batch-1`  
**Base:** `main`  
**Max URLs:** 5  
**Auto-Merge:** FALSE (Human review required)  
**Parent Decision:** Issue #844 concluded `READY FOR JULES` on 2026-10-19.

---

## 1. Overview & Constraints

Jules is tasked with executing a purely mechanical, bounded AEO retrofit across exactly 5 prioritized URLs.

> [!IMPORTANT]
> **Strict Boundaries for Jules:**
> - NO invented professional recommendations, methods, or clinical claims in Shira's name.
> - NO fabricated client cases, statistics, percentages, or research.
> - NO changes to entity credentials (Shira is a couples counselor and parenting guide; NOT a psychologist or psychotherapist).
> - NO FAQPage JSON-LD additions on blog/pillar pages.
> - NO new URLs.
> - Set truthful `updatedAt: "2026-10-19"` only on articles where content actually changed.
> - NO auto-merge.

---

## 2. Target URLs and Exact Changes

### URL 1: `/blog/breaking-silent-treatment-relationship`
- **File:** `src/data/posts.json` (ID: `breaking-silent-treatment-relationship`)
- **Direct Answer to add:**
  ```json
  "directAnswer": "שבירת שתיקה מענישה (Silent Treatment) בזוגיות מתחילה בהכרה בכך ששתיקה היא דפוס התגוננות ולא פתרון. הצעד הראשון הוא להפסיק להפעיל לחץ לשבירת השתיקה, לאפשר מרחב רגיעה קצר, ולאחר מכן לפתוח בשיחה ממוקדת בגוף ראשון על תחושת הניתוק ולא על האשמות הדדיות."
  ```
- **Internal Links to verify/add:**
  - Link to `/services/couples` using anchor text "ייעוץ זוגי".
  - Link to `/blog/defensiveness-in-relationships`.
- **Date update:** `"updatedAt": "2026-10-19"`

### URL 2: `/blog/gifted-children-framework-preparation`
- **File:** `src/data/posts.json` (ID: `gifted-children-framework-preparation`)
- **Direct Answer to add:**
  ```json
  "directAnswer": "הכנה למסגרת מחוננים (כיתת מחוננים או יום שליפה) מתמקדת בתיאום ציפיות רגשי ולא בהאצה לימודית: מתן לגיטימציה לקושי אפשרי, הכנה לקצב למידה שונה ולמפגש עם קבוצת שווים, והדגשת ערך המאמץ וההתנסות על פני ציונים או הצלחה מיידית."
  ```
- **Internal Links to verify/add:**
  - Link to `/services/gifted-parenting` using anchor text "הנחיית הורים למחוננים".
- **Date update:** `"updatedAt": "2026-10-19"`

### URL 3: `/blog/smart-youth-focus-tasks-organization`
- **File:** `src/data/posts.json` (ID: `smart-youth-focus-tasks-organization`)
- **Direct Answer to add:**
  ```json
  "directAnswer": "כאשר נער נבון מתקשה בביצוע משימות ובהתארגנות, הקושי נובע לרוב מפערי תפקודים ניהוליים ולא מחוסר יכולת או עצלנות. המענה ההורי היעיל כולל פירוק משימות גדולות לשלבים קונקרטיים, יצירת עוגני זמן חיצוניים, וצמצום עומס הבחירה ללא כעס או מאבקי שליטה."
  ```
- **Internal Links to verify/add:**
  - Link to `/services/gifted-parenting` using anchor text "הדרכת הורים למחוננים".
  - Link to `/blog/gifted-adhd-executive-functions-struggle`.
- **Date update:** `"updatedAt": "2026-10-19"`

### URL 4: `/blog/defensiveness-in-relationships`
- **File:** `src/data/posts.json` (ID: `defensiveness-in-relationships`)
- **Direct Answer to add:**
  ```json
  "directAnswer": "התגוננות בזוגיות היא תגובה אוטומטית לתחושת איום או ביקורת, שבה בן הזוג מסביר, מצטדק או תוקף בחזרה. יציאה ממעגל ההתגוננות דורשת עצירה מודעת של הוויכוח, לקיחת אחריות על חלק קטן מהקושי והקשבה לרגש שמאחורי דברי הצד השני במקום למילים המדויקות."
  ```
- **Internal Links to verify/add:**
  - Link to `/services/couples` using anchor text "ייעוץ זוגי".
  - Link to `/blog/breaking-silent-treatment-relationship`.
- **Date update:** `"updatedAt": "2026-10-19"`

### URL 5: `/services/couples-aliyah-relocation`
- **File:** `src/pages/Services/Relocation/CouplesAliyahRelocationPage.tsx`
- **Direct Answer block to add:**
  Add a focused, accessible callout block highlighting the core dynamics:
  ```tsx
  <div className={styles.directAnswerBox} role="region" aria-label="תמצית מענה על זוגיות ברילוקיישן">
    <p>
      <strong>מענה ישיר:</strong> מעבר רילוקיישן או עלייה מפגיש זוגות עם פערי הסתגלות, שינויי תפקידים ואובדן רשת תמיכה טבעית. ליווי זוגי ממוקד מסייע לבסס תיאום ציפיות מחודש, לחלק מחדש עומסים רגשיים ומעשיים, ולשמור על הזוגיות כעוגן יציב בתקופת המעבר.
    </p>
  </div>
  ```
- **Internal Links to verify/add:**
  - Contextual link to `/blog/returning-to-israel-after-relocation-relationship` in the adaptation or return challenges section.

---

## 3. Required Automated Gates

Before opening PR for review, Jules must execute and pass 100% of the following:

1. `npm run generate` — regenerate summaries, sitemap, llms-full, RSS.
2. `npm run lint` — 0 errors.
3. `npm run test:content` — validate 118+ posts.
4. `npm test` — all vitest tests pass (including `aeo-foundation.test.ts`).
5. `npm run typecheck` — tsc passes with 0 errors.
6. `npm run build && npm run verify:dist` — all prerendered routes valid, matching canonicals, no duplicate tags.
