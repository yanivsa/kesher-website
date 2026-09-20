# W1-01 Editorial Draft: ייעוץ זוגי אונליין

## Editorial Metadata
- Wave ID: W1-01
- Action: UPDATE_EXISTING
- Target URL: /services/couples
- Primary intent: ייעוץ זוגי אונליין
- Primary query: ייעוץ זוגי אונליין
- Evidence strength: HIGH
- Confidence: HIGH

## Current-page diagnosis
The current couples service page already states that counseling is available in Ashdod and online (Zoom), and already states that sessions last 50 minutes. What is missing is a dedicated section that answers the online-intent questions clearly without creating a competing URL.

## Final proposed copy
[Recommended placement: before the existing section "מתי צריך מענה אחר או נוסף?"]

## איך עובד ייעוץ זוגי אונליין?

אם קשה לכם להגיע לקליניקה באשדוד בגלל מרחק, שעות עבודה, מגורים בחו״ל או תקופה של רילוקיישן, אפשר לקיים את פגישת הייעוץ הזוגי גם אונליין בזום. הפגישה נמשכת 50 דקות, ובמהלכה עובדים על אותם נושאים שמביאים זוגות לייעוץ: דפוסי שיחה שחוזרים על עצמם, קונפליקטים, ריחוק, תיאום ציפיות וקבלת החלטות משותפת.

**איך מתכוננים לפגישה אונליין?**
- בחרו מקום שבו שניכם יכולים לדבר בפרטיות וללא הפרעות.
- נסו להתחבר כמה דקות מראש ולבדוק שהמצלמה, הקול והחיבור לאינטרנט עובדים.
- אם אפשר, שבו מול מחשב או מסך שמאפשר לשניכם להשתתף בנוחות.
- כדאי לפנות את זמן הפגישה ולא לנסות לקיים אותה במקביל לטיפול בילדים, נהיגה או משימות אחרות.

**מתי הפורמט יכול להיות שימושי?**
אונליין יכול להיות פתרון מעשי לזוגות שאינם גרים באשדוד, לזוגות שנמצאים בתקופת מעבר או רילוקיישן, או כששגרת החיים מקשה על הגעה קבועה לקליניקה. אם יש נסיבות שמקשות לקיים שיחה זוגית בטוחה ופרטית מהבית, אפשר לברר מראש מהו הפורמט המתאים יותר.

לזוגות שנמצאים בתהליך עלייה, רילוקיישן או חזרה לישראל יש גם מידע ממוקד בעמוד [ייעוץ זוגי לעולים ולזוגות ברילוקיישן](/services/couples-aliyah-relocation).

## Suggested SEO title
KEEP_CURRENT_TITLE

## Suggested meta description
KEEP_CURRENT_META

## Internal links
- "ייעוץ זוגי לעולים ולזוגות ברילוקיישן" → /services/couples-aliyah-relocation
- local/in-person option → /couples-counseling-ashdod
- booking → /appointment

## Sources used
- Repository service facts: `/services/couples` already states that sessions are in Ashdod or online and last 50 minutes.
- Repository FAQ: online counseling is an existing service offering.

## Claims requiring business verification
None.

## Implementation notes for Phase 5
Add this as a dedicated section in `CouplesCounseling.tsx`, preserving the existing page title, metadata, schema and overall service intent. Do not add claims that Zoom is "secure", encrypted, or unrecorded unless separately verified as a business/platform practice.
