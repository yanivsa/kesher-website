import React from 'react';
import ServicePageTemplate from '../../../components/ServicePageTemplate/ServicePageTemplate';
import styles from './ParentingGuidance.module.css';

const ParentingGuidance: React.FC = () => {
  const content = (
    <div className={styles.serviceContent}>
      <section className={styles.segment}>
        <h2>למי זה מתאים?</h2>
        <p>הדרכת הורים היא המקום שבו אנחנו הופכים מהורים ש'מכבים שריפות' להורים שמובילים את הבית. זה מתאים לכם אם:</p>
        <ul>
          <li>הבית הפך לשדה קרב של מאבקי כוח וויכוחים.</li>
          <li>אתם מרגישים חסרי אונים מול התנהגויות של הילדים.</li>
          <li>קיבלתם אבחון ADHD ואתם רוצים לדעת איך לעזור לילד באמת.</li>
          <li>יש לכם חילוקי דעות קשים עם בן הזוג על הדרך החינוכית.</li>
        </ul>
      </section>

      <section className={styles.segment}>
        <h2>התמחות ב-ADHD</h2>
        <p>הורות לילדי קשב וריכוז דורשת 'הפעלה' אחרת. אנחנו נלמד איך המוח שלהם עובד, איך לבנות שגרה שמורידה חיכוך, ואיך לשמור על הביטחון העצמי שלהם (ושלכם) בתוך האתגרים.</p>
      </section>

      <section className={styles.segment}>
        <h2>איך נראה התהליך?</h2>
        <div className={styles.steps}>
          <div className={styles.step}>
            <h3>1. הבנת המנגנון</h3>
            <p>ננתח את הסיבות האמיתיות להתנהגות ונלמד מה הילד מנסה 'להגיד' לנו.</p>
          </div>
          <div className={styles.step}>
            <h3>2. יצירת סמכות מטיבה</h3>
            <p>נבנה כלים להצבת גבולות ברורים מתוך חיבור ואהבה, בלי צעקות.</p>
          </div>
          <div className={styles.step}>
            <h3>3. שיפור האווירה</h3>
            <p>נחזיר את השקט והנאה המשפחתית לבית שלכם.</p>
          </div>
        </div>
      </section>
    </div>
  );

  return (
    <ServicePageTemplate
      title="הדרכת הורים אשדוד | ADHD | שירה סהרוני"
      description="הדרכת הורים מקצועית באשדוד. התמחות בילדים עם ADHD, הצבת גבולות ושיפור האווירה המשפחתית."
      heroTitle="הדרכת הורים"
      heroSubtitle="להפוך מהורים ששורדים את היום להורים שמובילים בביטחון."
      icon="👨‍👩‍👧"
      image="/images/generated/services/parenting-room.jpg"
      content={content}
    />
  );
};

export default ParentingGuidance;
