import React from 'react';
import MetaTags from '../../components/SEO/MetaTags';
import styles from './LegalPage.module.css';

const AccessibilityPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags
        title="הצהרת נגישות — שירה סהרוני | קשר"
        description="הצהרת הנגישות הרשמית של אתר שירה סהרוני. אנו פועלים להנגשה מלאה של האתר והקליניקה באשדוד לכלל האוכלוסייה."
        canonical="https://kesher.saharoni.com/accessibility"
      />
      <header className={styles.header}>
        <div className="container">
          <h1>הצהרת נגישות</h1>
        </div>
      </header>
      <div className="container">
        <div className={styles.content}>
          <p>
            אני רואה חשיבות עליונה במתן שירות שוויוני, מכבד ונגיש לכלל הגולשים והלקוחות, מתוך אמונה כי לכל אדם מגיעה הזדמנות שווה ליהנות משירותי ייעוץ, הדרכה וגישור.
          </p>

          <h2>1. נגישות הדיגיטל והאתר</h2>
          <p>
            האתר נבנה ומתוחזק תוך שאיפה לעמוד בדרישות תקנות שוויון זכויות לאנשים עם מוגבלות (התאמות נגישות לשירות), התשע"ג-2013, ובתקן הישראלי <b>ת"י 5568 ברמת AA</b> (המבוסס על הנחיות WCAG 2.0).
          </p>
          <p>התאמות הנגישות שבוצעו באתר כוללות:</p>
          <ul>
            <li><b>ניווט מקלדת:</b> תמיכה מלאה בטרגוט פוקוס ברור ומקשי Tab / Shift+Tab.</li>
            <li><b>קישור דילוג:</b> אפשרות דילוג ישיר לתוכן המרכזי (Skip to Content).</li>
            <li><b>תמיכה בקוראי מסך:</b> שימוש באלמנטים סמנטיים (HTML5), תגיות ARIA ומבנה כותרות היררכי.</li>
            <li><b>התאמת רגישות לתנועה:</b> תמיכה מלאה בהגדרות הדפדפן להפחתת תנועה (prefers-reduced-motion) המבטלת הנפשות כבדות.</li>
            <li><b>ניגודיות וטיפוגרפיה:</b> יחס ניגודיות צבעים גבוה ופונטים קריאים מבית Google Fonts (היבו / פרנק רול).</li>
            <li><b>נגישות מובייל:</b> התאמה מלאה למסכי מגע, הגדלת תצוגה בדפדפן וגבהי מסך דינמיים (100svh).</li>
          </ul>

          <h2>2. נגישות פיזית בקליניקה באשדוד</h2>
          <p>
            הפגישות הפרונטליות מבוצעות בטרקלין ייעוץ וגישור שקט ונגיש באשדוד. במידה ונדרשות התאמות נגישות פיזית ספציפיות, חניה נגישה או ליווי, אשמח שתיצרו עמי קשר מראש כדי שאדאג לכל ההתאמות הנדרשות.
          </p>

          <h2>3. רכזת ואשת קשר בנושאי נגישות</h2>
          <p>
            אם נתקלתם בבעיה, קושי או רכיב שאינו נגיש מספיק באתר או בקליניקה, אשמח שתעדכנו אותי על כך ואפעל לתיקון המענה בהקדם.
          </p>

          <div className="bg-[#181820] border border-[#2d2d3d] p-4 rounded-xl my-4">
            <p className="font-bold text-white mb-1">רכזת הנגישות:</p>
            <p className="text-gray-300">שירה סהרוני</p>
            <p className="text-gray-300">אימייל לפניות נגישות: <b>shira@saharoni.com</b></p>
            <p className="text-[#E5C158] text-sm mt-2">מענה יינתן בתוך 2 ימי עסקים.</p>
          </div>

          <p className="mt-8 text-sm text-gray-500">עדכון אחרון: אוגוסט 2026</p>
        </div>
      </div>
    </div>
  );
};

export default AccessibilityPage;
