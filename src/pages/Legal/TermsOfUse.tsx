import React from 'react';
import MetaTags from '../../components/SEO/MetaTags';
import styles from './LegalPage.module.css';

const TermsOfUse: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags title="תנאי שימוש | שירה סהרוני" description="תנאי השימוש באתר שירה סהרוני. אנא קראו את התנאים בקפידה לפני הגלישה באתר." />
      <header className={styles.header}>
        <div className="container">
          <h1>תנאי שימוש</h1>
        </div>
      </header>
      <div className="container">
        <div className={styles.content}>
          <p>השימוש באתר שירה סהרוני כפוף לתנאים המפורטים להלן. הגלישה באתר מהווה הסכמה לתנאים אלו.</p>
          
          <h2>תוכן האתר</h2>
          <p>המידע והמאמרים המופיעים באתר נועדו לצורך העשרה ומידע כללי בלבד. אין לראות במידע זה תחליף לייעוץ זוגי או הדרכת הורים מקצועית המותאמת אישית לצרכיכם.</p>

          <h2>קניין רוחני</h2>
          <p>כל זכויות הקניין הרוחני באתר, לרבות המאמרים, העיצוב, הקוד והתמונות, שייכים לשירה סהרוני (או לצדדים שלישיים שהתירו את השימוש בהם). אין להעתיק או להפיץ תוכן מהאתר ללא אישור מראש ובכתב.</p>

          <h2>הגבלת אחריות</h2>
          <p>שירה סהרוני לא תישא באחריות לכל נזק שייגרם כתוצאה משימוש באתר או הסתמכות על התכנים המופיעים בו.</p>
          
          <p>עדכון אחרון: מאי 2026</p>
        </div>
      </div>
    </div>
  );
};

export default TermsOfUse;
