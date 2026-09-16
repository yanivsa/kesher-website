# דוח סיום שלב 3: פיילוט מבוקר AEO (Phase 3 Report)

**ענף:** `aeo/controlled-pilot`  
**PR:** [#835](https://github.com/yanivsa/kesher-website/pull/835) (`aeo/controlled-pilot -> aeo/technical-foundation`)  
**בסיס אב:** `aeo/technical-foundation` (`14c5c211`)  

---

## 1. תקציר ביצוע

הושלם במלואו שלב הפיילוט המבוקר (Controlled Pilot) על גבי הענף המבודד `aeo/controlled-pilot`.
השלב יישם בדיוק את מטרות שלב 3 ללא הרחבת יתר או שכתוב המוני:
1. **יקום פרומפטים מורחב ומדויק (`docs/aeo/prompt-universe.csv`):** 150 שאילתות שיחה מציאותיות בעברית בחלוקה ל-4 מבצרי התוכן + שכבה מקומית אשדוד + שלבי מסע הפונה.
2. **מודיעין ציטוטים ופערי אזכור (`docs/aeo/citation-gap.md`):** ניתוח עובדות מבוססות מול השערות, פערים מול מתחרים מבוססי סמכות, ואיפה בדיוק מנועי תשובות נכשלים במציאת "קשר".
3. **מיפוי קלט מומחה נדרש (`docs/aeo/expert-input-needed.md`):** שאלות ממוקדות לשירה עבור עמודי שירות ומאמרי מפתח, תוך הקפדה על גבולות אתיקה (ללא המצאת נתונים/מקרים פיקטיביים).
4. **מפת קישוריות פנימית היררכית (`docs/aeo/internal-link-map.md`):** ארכיטקטורת Hub & Spoke מלאה עם עוגנים עבריים טבעיים המחברים בין עמודי השירות למאמרי העומק.
5. **ביצוע ניסוי מבוקר על 5 כתובות פיילוט (`docs/aeo/experiments.csv`):** בדיקת 5 היפותזות נפרדות למדידת אפקטיביות תשובות AI, CTR, וסמכות מקומית.

> [!NOTE]
> **הבהרת שיוך ענפים עבור 5 כתובות הפיילוט:**
> סך הכל 5 כתובות טופלו בפרויקט. מתוכן, כתובת 1 (`/couples-counseling-ashdod`) שודרגה ונכללה בענף התשתית הטכנית (`aeo/technical-foundation`), בעוד 4 הכתובות הנותרות (עמוד שירות 1 ו-3 מאמרי בלוג) שודרגו ישירות בענף הפיילוט (`aeo/controlled-pilot`).

---

## 2. חמשת דפי הפיילוט בפרויקט (The 5 Pilot URLs)

| URL | קובץ מקור | ענף שינוי | היפותזה שנבדקה | יישום בפועל שנבדק ואומת |
|---|---|---|---|---|
| `/couples-counseling-ashdod` | `src/pages/Landing/CouplesCounselingAshdod/CouplesCounselingAshdodPage.tsx` | `aeo/technical-foundation` | חיזוק סכמת Service וסמכות מקומית באשדוד ישלול הזיות גיאוגרפיות | נורמל ל-`Service` עם `provider: #business`, שיוך שירה, ותגיות אזור מקומיות מדויקות. |
| `/services/gifted-parenting` | `src/pages/Services/Gifted/GiftedParentingPage.tsx` | `aeo/controlled-pilot` | הפיכת עמוד שירות ל-Topic Pillar עם תוכן FAQ גלוי ואיכותי וקישוריות אשכול מעלה הכללה ב-AI | מדור שאלות נפוצות גלוי בהבחנה מאוזנת ומשלימה בין הנחיית הורים לטיפול רגשי, הסרת סכמת `FAQPage` מגרף ה-JSON-LD (לאור ביטול FAQ rich results בגוגל במאי 2026 ומדיניות הימנעות מסכמות ספקולטיביות), ובלוק קישורים ל-6 מאמרי מחוננות. |
| `/blog/gifted-adhd-executive-functions-struggle` | `src/data/posts.json` | `aeo/controlled-pilot` | Direct Answer תמציתי ומקורות סמכות מאומתים יזכו בציטוט AI מדויק ללא יומרה אבחונית | הוספת `directAnswer` בשפה מסויגת, `updatedAt: "2026-09-16"`, מאמר סקירה אקדמי בביקורת עמיתים (Foley-Nicpon et al., 2011 ב-Gifted Child Quarterly), משרד החינוך (מדיניות פדגוגית), ו-SENG. |
| `/blog/newlywed-first-year-conflicts` | `src/data/posts.json` | `aeo/controlled-pilot` | פסקת תשובה תמציתית וטבלת החלטה מובנית במריבות השנה הראשונה מקפיצות ציטוט השוואתי | הוספת `directAnswer` תמציתי ("מוקדי מחלוקת נפוצים יכולים לכלול"), `updatedAt: "2026-09-16"`, מסגור ניהול כספי ככלי/אפשרות ולא כחוק גורף, וטבלת השוואה מובנית. |
| `/blog/returning-to-israel-after-relocation-relationship` | `src/data/posts.json` | `aeo/controlled-pilot` | מענה ממוקד לשאלת "הלם תרבות הפוך" עם מקור מחקרי סמכותי יבסס מובילות בנישה | הוספת `directAnswer` מסויג ("עשויה לסייע להתארגן מחדש"), `updatedAt: "2026-09-16"`, מחקר אמפירי בביקורת עמיתים (Sussman, 2002) המובחן מההמלצות הזוגיות המעשיות. |

---

## 3. קבצים שנוצרו ועודכנו (Files Created & Modified)

### תיעוד AEO ייעודי:
- `docs/aeo/prompt-universe.csv` (150 פרומפטים מובנים)
- `docs/aeo/citation-gap.md` (ניתוח פערים ומודיעין תשובות)
- `docs/aeo/expert-input-needed.md` (שאלון קלט מומחה ממוקד לשירה)
- `docs/aeo/internal-link-map.md` (מיפוי Hub & Spoke מלא)
- `docs/aeo/experiments.csv` (מפרט 5 הניסויים ומדדי בקרה 30d/60d)
- `docs/aeo/monitoring-prompts.csv` (35 פרומפטים נבחרים לניטור תקופתי)
- `docs/aeo/external-entity-plan.md` (תוכנית ישות חיצונית, אינדקסים, GBP ווידאו)
- `docs/aeo/jules-rollout-plan.md` (גבולות אוטומציה ושערי בקרה לג'ולס)
- `docs/aeo/phase-3-report.md` (דוח זה)

### קוד ותוכן:
- `src/pages/Services/Gifted/GiftedParentingPage.tsx` (שימור שאלות נפוצות גלויות, הסרת סכמת FAQPage, והטמעת בלוק מאמרי מחוננות מקושרים)
- `src/data/posts.json` (הטמעת `directAnswer`, `updatedAt: "2026-09-16"`, טבלה ומקורות מאומתים ב-3 מאמרי הפיילוט)
- `src/data/postSummaries.json`, `public/sitemap.xml`, `public/llms-full.txt`, `public/rss.xml` (סנכרון מלא באמצעות `npm run generate`)

---

## 4. תוצאות אימות טכני ובדיקות דפדפן (Technical Verification & Browser QA)

- **[VERIFIED] שלמות מקורות וראיות (Source Integrity):** 100% מהמקורות ב-`evidence` נבדקו ונמצאו מחזירים HTTP 200 (קישורי 404 תוקנו, כולל קישור למרחב הפדגוגי של משרד החינוך, מחקר סקירה אקדמי של Foley-Nicpon et al. 2011, ומחקר Sussman 2002 ב-Elsevier/IJIR).
- **[VERIFIED] סכמות ונתוני תוכן:** `scripts/validate-content.cjs` עבר בהצלחה מלאה ללא שגיאות. תגיות `lastmod` ב-`public/sitemap.xml` עודכנו בדיוק עבור 3 המאמרים ל-`2026-09-16`.
- **[VERIFIED] בדיקות יחידה וסמכות:** כל 18 קובצי בדיקות ה-Vitest (86 בדיקות) עברו בהצלחה מלאה.
- **[VERIFIED] בדיקות מדיניות וידאו ובקרים:** 123 בדיקות פייתון עברו בהצלחה מלאה.
- **[VERIFIED] בדיקות דפדפן חיות (Browser QA via Playwright):** נבדקו 8 עמודים מייצגים (דף הבית, אודות, מאמר רגיל, וכל 5 עמודי הפיילוט) הן בתצוגת Desktop (1280x800) והן בתצוגת Mobile (390x844). כל 16 הבדיקות אישרו:
  * סטטוס HTTP 200 בכל העמודים.
  * כיווניות עברית מלאה (`dir="rtl"`).
  * אפס גלישה אופקית (`hasOverflow: false`).
  * רינדור תקין של שורת מחבר (Byline), תשובה ישירה (Direct Answer), טבלאות ורכיבי Evidence.
