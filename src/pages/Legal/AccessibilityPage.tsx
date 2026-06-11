import React from 'react';
import MetaTags from '../../components/SEO/MetaTags';
import styles from './LegalPage.module.css';

const AccessibilityPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags title="הצהרת נגישות | שירה סהרוני" description="הצהרת נגישות לאתר שירה סהרוני. אנו פועלים להנגשת האתר לכלל האוכלוסייה." />
      <header className={styles.header}>
        <div className="container">
          <h1>הצהרת נגישות</h1>
        </div>
      </header>
      <div className="container">
        <div className={styles.content}>
          <p>אני רואה חשיבות רבה במתן שירות שוויוני לכלל הגולשים ובשיפור חווית המשתמש באתר. אני משקיעה מאמצים רבים בהנגשת האתר ודפיו על מנת לאפשר לאנשים עם מוגבלות לגלוש בנוחות.</p>
          
          <h2>סטטוס נגישות</h2>
          <p>האתר נבנה ומתוחזק תוך שאיפה לעמוד בעקרונות WCAG ברמת AA. מתבצעות בדיקות אוטומטיות ושיפורים שוטפים, אך ייתכן שיתגלו אזורים שעדיין דורשים התאמה.</p>

          <h2>אמצעי נגישות באתר</h2>
          <ul>
            <li>ניווט פשוט וברור.</li>
            <li>תמיכה בקוראי מסך.</li>
            <li>אפשרות לשינוי גודל הגופן (באמצעות הדפדפן).</li>
            <li>ניגודיות צבעים תקינה.</li>
            <li>תמיכה בניווט מקלדת.</li>
            <li>טפסים נגישים.</li>
          </ul>

          <h2>יצירת קשר בנושאי נגישות</h2>
          <p>אם נתקלתם בבעיה או בתקלה בנושא הנגישות, אשמח שתעדכנו אותי על כך ואעשה מאמץ למצוא פתרון מתאים.</p>
          <p>ניתן לפנות אלי בדוא"ל: shira@saharoni.com</p>
          <p>עדכון אחרון: יוני 2026</p>
        </div>
      </div>
    </div>
  );
};

export default AccessibilityPage;
