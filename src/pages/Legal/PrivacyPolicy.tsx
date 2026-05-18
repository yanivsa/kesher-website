import React from 'react';
import MetaTags from '../../components/SEO/MetaTags';
import styles from './LegalPage.module.css';

const PrivacyPolicy: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags title="מדיניות פרטיות | שירה סהרוני" description="מדיניות הפרטיות של אתר שירה סהרוני. אנו מחויבים להגנה על פרטיות המשתמשים." />
      <header className={styles.header}>
        <div className="container">
          <h1>מדיניות פרטיות</h1>
        </div>
      </header>
      <div className="container">
        <div className={styles.content}>
          <p>פרטיות הגולשים חשובה לי מאוד. מסמך זה מפרט איזה מידע נאסף באתר וכיצד נעשה בו שימוש.</p>
          
          <h2>איסוף מידע</h2>
          <p>המידע שנאסף באתר כולל מידע שנמסר על ידכם מרצונכם החופשי בטפסים (שם, טלפון, אימייל) לצורך יצירת קשר ותיאום פגישות.</p>

          <h2>שימוש במידע</h2>
          <p>השימוש במידע יעשה אך ורק לצורך מתן השירות המבוקש על ידכם (חזרה לפנייה, משלוח המדריך החינמי). המידע אינו מועבר לצדדים שלישיים ללא הסכמתכם.</p>

          <h2>עוגיות (Cookies)</h2>
          <p>האתר עשוי להשתמש בעוגיות לצורך שיפור חווית המשתמש וסטטיסטיקות (כגון Google Analytics).</p>

          <h2>אבטחת מידע</h2>
          <p>אנו נוקטים באמצעי אבטחה מקובלים כדי להגן על המידע הנמסר באתר.</p>
          
          <p>עדכון אחרון: מאי 2026</p>
        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicy;
