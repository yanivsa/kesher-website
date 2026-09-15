# מפת קישורים פנימיים וגרף ידע אתרי (Internal Link Map)

ארכיטקטורת הקישוריות הפנימית מיועדת לחבר בין עמודי עוגן שירותיים (Hubs) לבין מאמרי עומק (Cluster Articles) באמצעות עוגנים בעברית טבעית (Natural Anchors), ללא דחיסה מלאכותית ומבלי לייצר לולאות קישור ספאמיות.

---

## 1. רשת הקישורים עבור 5 עמודי הפיילוט

```
+----------------------------------------------------------------------------------------------------+
|                                    ארכיטקטורת Hub & Spoke בפיילוט                                   |
+----------------------------------------------------------------------------------------------------+
                                      /services/gifted-parenting (Hub)
                                      ^            ^           ^
             +------------------------+            |           +-----------------------+
             |                                     |                                   |
             v                                     v                                   v
/blog/gifted-adhd-...                  /blog/smart-youth-...               /blog/gifted-children-...
(מחוננות ו-ADHD)                      (תפקודים ניהוליים)                  (פרפקציוניזם ובכי)

------------------------------------------------------------------------------------------------------

                                      /services/premarital-first-year (Hub)
                                      ^                        ^
             +------------------------+                        +-----------------------+
             |                                                                         |
             v                                                                         v
/blog/newlywed-first-year-conflicts                                /blog/marriage-prep-financial-...
(משברים בשנה הראשונה)                                             (שיחות על כסף לפני חתונה)

------------------------------------------------------------------------------------------------------

                                      /services/couples-aliyah-relocation (Hub)
                                      ^                        ^
             +------------------------+                        +-----------------------+
             |                                                                         |
             v                                                                         v
/blog/returning-to-israel-after-relocation-relationship            /blog/relocation-career-loss-...
(חזרה לארץ אחרי רילוקיישן)                                        (אובדן קריירה במעבר)
```

---

## 2. מפרט עוגני קישור מדויקים (Anchor Specifications)

| עמוד מקור | עמוד יעד | טקסט עוגן מומלץ (בעברית טבעית) | הקשר סמנטי במשפט |
|---|---|---|---|
| `/services/gifted-parenting` | `/blog/gifted-adhd-executive-functions-struggle` | "מחוננות לצד הפרעת קשב וקשיי התארגנות" | בהפניה למאמרי העומק של האשכול בסעיף הייעודי. |
| `/services/gifted-parenting` | `/blog/gifted-children-perfectionism-tears` | "התמודדות עם פרפקציוניזם ופחד מכישלון" | בהפניה למאמרי רגישות ותסכול. |
| `/services/gifted-parenting` | `/blog/gifted-children-framework-preparation` | "הכנה רגשית לכניסה למסגרת מחוננים" | בסקשן ההכנה למסגרת. |
| `/blog/gifted-adhd-executive-functions-struggle` | `/services/gifted-parenting` | "הנחיית הורים לילדים מחוננים" | בפסקת הסיכום וההפניה לשירות של שירה. |
| `/blog/newlywed-first-year-conflicts` | `/services/premarital-first-year` | "ליווי זוגי בשנה הראשונה לנישואים" | בפסקת ההנעה לפעולה ולבירור דפוסים. |
| `/blog/returning-to-israel-after-relocation-relationship` | `/services/couples-aliyah-relocation` | "ייעוץ זוגי לעולים ולזוגות ברילוקיישן" | בחלק העוסק בהסתגלות מחודשת ובניית עוגן. |
| `/couples-counseling-ashdod` | `/services/couples/crisis` | "ייעוץ זוגי במשבר" | בסקשן השאלות הנפוצות לגבי מקרים דחופים. |
| `/services/couples` | `/couples-counseling-ashdod` | "קליניקה לייעוץ זוגי באשדוד" | בסעיף אזורי שירות ואפשרויות פגישה. |
