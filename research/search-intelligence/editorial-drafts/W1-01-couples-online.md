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
The current couples counseling service page details the in-person offering in Ashdod but lacks information regarding the online consultation process. We are adding a section to explicitly explain how online sessions work, preserving all existing sections.

## Final proposed copy
[To be added under a new H2 section, perhaps just before "מתי צריך מענה אחר או נוסף?"]

## איך עובד ייעוץ זוגי אונליין?

זוגות רבים מגלים שדווקא המרחב המוכר של הבית מאפשר להם להיפתח בצורה שונה. ייעוץ זוגי אונליין דרך זום מספק מענה נוח וזמין לזוגות שמתקשים להגיע לקליניקה באשדוד בשל אילוצי זמנים, מרחק גיאוגרפי, משמרות בעבודה, או שהות בחו"ל ([רילוקיישן](/services/couples-aliyah-relocation)). 

**איך מתנהלת הפגישה?**
פגישת אונליין נמשכת 50 דקות, בדיוק כמו פגישה בקליניקה. המטרה, הכלים והגישה נותרים זהים – יצירת שיח בטוח, הבנת מעגלי המריבה ומתן כלים מעשיים לתקשורת קרובה יותר.

**איך מתכוננים לפגישת אונליין?**
- בחרו חדר שקט בבית שבו תוכלו לשבת יחד, ללא הסחות דעת וללא ילדים שמתרוצצים ברקע.
- ודאו שיש לכם חיבור אינטרנט יציב.
- מומלץ להתחבר ממחשב נייד או מסך גדול (ולא מהנייד), כדי שתוכלו לשבת בנוחות אחד ליד השנייה.

**למי זה מתאים?**
ייעוץ זוגי אונליין מתאים מאוד כשאתם מחפשים לשפר את התקשורת, לפתור קונפליקטים או לעשות הכנה משמעותית לקראת נישואים. עם זאת, במצבי משבר חריפים מאוד, או כשנדרש טיפול זוגי מקיף הנוגע לפגיעות עמוקות, לעיתים אמליץ להתחיל במפגשים פרונטליים, שם ניתן להחזיק את המרחב הרגשי מקרוב.

הפרטיות שלכם חשובה. השיחות מתקיימות דרך קישור מאובטח ואינן מוקלטות בשום שלב.

## Suggested SEO title
KEEP_CURRENT_TITLE

## Suggested meta description
KEEP_CURRENT_META

## Internal links
- "רילוקיישן" → /services/couples-aliyah-relocation

## Sources used
None required (factual service offering).

## Claims requiring business verification
- Is the duration exactly 50 minutes for online sessions?
- Is it OK to explicitly state that Zoom links are secure and not recorded?

## Implementation notes for Phase 5
Add this section to `CouplesCounseling.tsx` as a new `<section>` before or after the "מתי צריך מענה אחר או נוסף?" section. Use appropriate icons/styling consistent with the page.
