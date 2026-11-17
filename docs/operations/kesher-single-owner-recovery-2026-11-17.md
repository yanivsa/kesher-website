# KESHER — הוכחות, תקלה נוכחית, ומסלול התאוששות יחיד

**תאריך בדיקה: 17.11.2026 (Asia/Jerusalem). מצב: תיעוד ואבחון בלבד.**
המסמך אינו מפעיל ייצור, משנה בעלות או יוצר בקר/תזמון/משימה חדשים. 
המערכת הקנונית: yanivsa/kesher-website; בקר אחד, מקור אחד, שלושה נכסים מאומתים.

## מה עבד בעבר (הוכחות ישירות)

| אירוע | הוכחה | מסקנה מוגבלת |
| --- | --- | --- |
| שורט מקורי, 9.11 | [Actions 42568587136](https://github.com/yanivsa/kesher-website/actions/runs/42568587136), success | kesher-short-v4 היה מסוגל להפיק ולהעלות דרך הרשאות קיימות; success לא מחליף בדיקת תוכן וקול |
| חידוש שורט, 15.11 | [Actions 43762909927](https://github.com/yanivsa/kesher-website/actions/runs/43762909927), success | אפשר לחדש את הפריט הקיים במקום ליצור משימת NotebookLM כפולה |
| מאמר + מיפוי וידאו, 15.11 | [Deploy 43764446017](https://github.com/yanivsa/kesher-website/actions/runs/43764446017), success | הפריסה בוצעה; עדיין נדרשת בדיקת קישורים ציבוריים |
| מאמר 16.11 | [Deploy 43960923892](https://github.com/yanivsa/kesher-website/actions/runs/43960923892), success | main בגרסת 0c9af18ee96374a0b9b56742947b480af7e54cc1 נפרס; העמוד https://kesher.saharoni.com/blog/child-led-play-10-minutes-connection אומת ישירות באתר |
| ניטור 17.11 | [Watchdog 44005064419](https://github.com/yanivsa/kesher-website/actions/runs/44005064419), success | **זה לא אישור לפעילות ייצור**: הלוג מציג LIVENESS_BLOCKED_STALE_ACTIVE_RUN ו־KESHER_DAILY_PREFLIGHT: ARTICLE_NOT_IN_MAIN, NOT_ATTESTED, UNVERIFIED_EXTERNAL |

## גורם שורש מאומת ב־17.11

1. בקובץ הקנוני automation-state:.kesher-controller/state.json נמצאו schema_version=5, cycle=2026-11-08, updated_at=2026-11-08T20:50:56.333997+00:00. זה **לא** אישור למעבר Schema-6.
2. בקר Kesher Content Controller הישן, workflow ID 337960554, מושבת. הריצה הישנה [42522546178](https://github.com/yanivsa/kesher-website/actions/runs/42522546178) עדיין queued ללא עדכון מאז 8.11; היא אינה הוכחה לעבודה פעילה.
3. Cloudflare kesher-heartbeat קיים, cron כל חמש דקות, אך מפנה ל־kesher-content-controller.yml המושבת. העובדה שיש שעון פעיל לא אומרת שהבקר מופעל.
4. [PR #1267](https://github.com/yanivsa/kesher-website/pull/1267) כבר מוזג ומספק קוד בטיחות. מיזוג קוד אינו התקנה של gateway עצמאי או הוכחת בעלות.
5. לא נמצא אישור עצמאי להפעלת gateway מוגן, ששת גבולות המשאבים, owner/epoch/CAS ו־KESHER_CUTOVER_GATEWAY_URL. אין להמציא כתובת, מפתחות או אישורים.
6. ב־main: src/data/postsRecent.json מסתיים ב־16.11; במיפוי src/data/articleVideos.json אין וידאו למאמר 16.11, וב־17.11 לא אומתה שלישיית נכסים. סרטוני יום קודם אינם משלימים את היום.

## המשך נכון — שלב אחד בטוח בכל ריצה

**1. תצפית:** התאריך בישראל, שתי רשימות המאמרים, PR פתוחים, latest main, workflow runs כולל queued, ה־artifacts, מצב controller מתוך automation-state, Cloudflare production commit, ורק קישורים ציבוריים אמיתיים. בדוק מזהי משימות NotebookLM/YouTube קיימות לפני כל יצירה.

**2. דווח מצב יחיד עם ראיות:** ARTICLE_MISSING, ARTICLE_PUBLIC, WAITING_PROVIDER, QA_HOLD, WAITING_PUBLIC, BLOCKED_OWNER_GATEWAY או DONE_3_PUBLIC. לכל סטטוס: slug, content SHA, run ID, task/item ID אם קיים, timestamp, קישור ראיה וצעד הבא יחיד. הצלחת CI/Watchdog אינה DONE.

**3. תיקון תשתית, פעם אחת:** פעל לפי [הוראות התקנת השרת המוגן](kesher-cutover-host.md) ו[חוזה האספקה](kesher-durable-delivery.md). מנהל עצמאי חייב להתקין שירות עמיד עם ledger, הרשאות נפרדות, סקירה וחתימה על הקוד, OIDC מוגן וגבולות משאב Native אמיתיים עבור GitHub, Jules, NotebookLM, YouTube, Cloudflare וספק התמונה. דרושים הוכחת retire/drain של הבקר הישן, owner/epoch/CAS וקריאת מצב מקורית מכל שירות. אין לקבל 'הכל ירוק' כתחליף לבדיקה. GPT Actions הוא לקוח נוסף, לא תחליף לגדר הרשאות. אם אין מנהל/גישה — BLOCKED_OWNER_GATEWAY עם דרישת פעולה קונקרטית, לא ניסיונות הפקה.

**4. מעבר מבוקר:** לפני cutover נדרש preflight רק-קריאה בשרת המוגן, בדיקת קוד/מדיניות/הרשאות exact SHA, ולאחריה צעדי cutover ידניים מוגנים דרך ה־workflow הקיים kesher-production-cutover.yml. בצעד לא ודאי בודקים קודם יומן persisted ולא חוזרים אוטומטית. לא משנים ידנית automation-state, לא מפעילים את Schema5 הישן, ולא מכוונים heartbeat לבקר אחר לפני שמוכחת בעלות יחידה.

**5. בדיקת קבלה אחת:** לאחר אישור VERIFIED אמיתי, הפעל רק את הבקר היחיד לבדיקת מקור E2E אחת, וודא CAS לפני dispatch, חידוש אותה משימת provider לפי Task ID, ו־duplicate wake שהוא NOOP. רק אז השתמש ב־heartbeat Cloudflare הקיים (לא ליצור cron חדש).

**6. מאמר:** תאריך ישראל ומאמר אחד, נושא בעל אישור, כותרת שאלה שימושית, תשובה ב־1–2 המשפטים הראשונים, מקורות מחקריים מדויקים ותמונת Hero מתאימה ובעלת זכויות. PR, בדיקות איכות על ה־head המדויק, מיזוג בטוח, פריסה קיימת, HTTP 200/title/canonical/hero. מאמר שכבר פורסם לא מייצרים שוב.

**7. וידאו ארוך:** NotebookLM למקור המדויק, task ID אחד, WAITING_PROVIDER נשמר ומנוטר באותה משימה. בדיקת מקור, קול נשי בעברית, רמת חזות, אודיו, זכויות, hash. העלאה אחת ל־YouTube, ואימות ציבוריות בפועל.

**8. שורט:** רק אחרי Long ציבורי, NotebookLM native 9:16 עצמאי, קשירת slug/content SHA/Long item ID הזוכה. חידוש task קיים אם קיים, בקרת קול וחזות, העלאה אחת, אימות שורט ציבורי.

**9. הטמעה והשלמה:** עדכון מיפוי src/data/articleVideos.json ב־PR מאומת, Cloudflare deploy, אימות נגן click-to-play לאחר לחיצה. DONE רק עם URL מאמר, Long ו־Short ציבוריים תואמים, מקור/תאריך/ SHA, run IDs והוכחות.

**10. כישלון חוזר:** אל תיצור פקודה זהה. שמור fingerprint של התקלה והשלב ב[Issue #1210 הקיים](https://github.com/yanivsa/kesher-website/issues/1210), שייך בעלים וצעד אחד, תקן קוד עם regression test ובדוק exact-head CI. דווח למשתמש רק על שינוי מהותי או פעולה בלעדית הנדרשת ממנו. אין משימות מתוזמנות נוספות ואין Rube.

## שער קבלה — לא לפרסם 'נפתר' לפני שהכול הוכח

- [ ] שרת gateway עצמאי ומוגן הותקן עם ledger מתמיד.
- [ ] משתנה סביבת kesher-cutover KESHER_CUTOVER_GATEWAY_URL תואם לשרת TLS + OIDC מוגן ואומת חיצונית.
- [ ] ששת משאבי ההפקה מוגנים ב־Native exclusion ולא בהצהרת קוד.
- [ ] owner/epoch/מדיניות pinned/הרשאות ומעבר CAS מתועדים ומאומתים.
- [ ] הריצה הישנה והסמכויות הוותיקות סולקו בבטחה; בקר יחיד באמת פעיל.
- [ ] אותו provider task ממשיך אחרי WAITING; wake כפול אינו מפיק פעמיים.
- [ ] heartbeat הישן מצביע רק לבקר החדש לאחר אישור מעבר.
- [ ] לכל יום מאמר, Overview ו־Short ציבוריים עם קישורים והטמעה.

**מסמך זה אינו אישור production cutover, אינו מצדיק הפעלת מסלול ישן או יצירת כפילויות.**


## דוגמאות היסטוריות שאומתו מתוך Issue #1210 (בדיקת עומק)

**26.10 — municipal-kindergarten-adjustment:** 
[מאמר](https://kesher.saharoni.com/blog/municipal-kindergarten-adjustment), [Long](https://youtu.be/FzAzvOP15Mo), [Short](https://youtu.be/xkLKquTygoQ). מזהה מקור d4ece4f847e979ca900a5c98f65bc5b4eecbe994f000d277a353753581f2d836; Long item video-20261026-131504-d4ece4f847-a2, משימת ספק 7120cf18-bee8-4481-bb22-cb1948f69d3f; Short item video-20261026-133251-d4ece4f847, משימת ספק 676c76d2-246b-4abf-abb0-1064ccca4cac. בקר ההפקה חידש את אותו הפריט לאחר עצירה, ללא שכפול. הריצה הייתה בסיוע ידני ולכן לא נחשבה מחזור אוטונומי נקי. **לקח:** הפרדת DONE_PUBLIC לבין CLEAN_AUTONOMOUS, וחידוש אותה משימה לאחר תקלה.

**2.11 — stool-withholding-potty-training:** 
[מאמר](https://kesher.saharoni.com/blog/stool-withholding-potty-training), [Long](https://youtu.be/xZotdUtnJXw), [Short](https://youtu.be/Yy15MJftfEY). נרשמו שלושה תוצרים ציבוריים תקינים טכנית, אבל ב־idea_history שויך בטעות idea_id של מאמר מחוננים לתוצרי הגמילה. **לקח:** התאמת idea_id/slug/content SHA היא שער עצמאות ותוכן, לא להסתפק בשלושה קישורים אקראיים. אין לשחזר או להעלות מחדש פריטים שכבר פורסמו בגלל שגיאת שיוך בלבד.

**6.11 — relationship-memory-reconstruction:** 
[מאמר](https://kesher.saharoni.com/blog/relationship-memory-reconstruction), [Long](https://youtu.be/VPUSEiBk2es). בדיקה מאומתת לחשבון YouTube אישרה Long ציבורי ומעובד בהצלחה, בעוד רישום המצב עדיין לא הושלם ו־Short נעצר בהמתנה לשיוך ה־Long. **לקח:** לא להעלות Long שני; לשחזר קודם את רישום ה־Long הציבורי ולחדש את ה־Short הקיים בכפוף למקור ובדיקת איכות.

מקור שלוש הבדיקות: [Issue #1210 והיסטוריית העדכונים בו](https://github.com/yanivsa/kesher-website/issues/1210) ב־26.10, 2.11 ו־6.11. אלה **דוגמאות לשחזור**, ולא הוכחה שהמערכת כיום מתפקדת או שפריט חסר יוצר מחדש.

