import React from 'react';
import { FiTarget, FiShield, FiMaximize } from 'react-icons/fi';
import { useScrollReveal } from '../../hooks/useScrollReveal';
import styles from './TrustSection.module.css';

const TrustSection: React.FC = () => {
  const [ref, isVisible] = useScrollReveal({ threshold: 0.1 });

  return (
    <section className={styles.trustSection}>
      <div className={`container ${styles.container}`} ref={ref}>
        <div className={`${styles.content} reveal ${isVisible ? 'visible' : ''}`}>
          <h2 className={styles.title}>סטנדרט מקצועי ללא פשרות</h2>
          <p className={styles.subtitle}>
            הליווי משלב הסתכלות זוגית והורית עם כלים מעשיים, כדי לתת לכם מענה רחב, פרקטי ומכבד.
          </p>
          <div className={`${styles.grid} reveal-stagger ${isVisible ? 'visible' : ''}`}>
            <div className={styles.card}>
              <div className={styles.iconWrapper}><FiShield aria-hidden="true" /></div>
              <h3>מרחב בטוח ללא שיפוטיות</h3>
              <p>מקום בטוח ודיסקרטי בו תוכלו להביא את עצמכם בדיוק כפי שאתם. הקשבה עמוקה, אמפתיה אמיתית והכלה של כל הקשיים והמורכבויות בדרך לפתרון.</p>
            </div>
            <div className={styles.card}>
              <div className={styles.iconWrapper}><FiTarget aria-hidden="true" /></div>
              <h3>כלים מעשיים לשגרת היום</h3>
              <p>התמקדות בפתרונות פרקטיים שתוכלו ליישם מיד. טכניקות לתקשורת מקרבת, כלים לניהול קונפליקטים וויסות רגשי במצבי לחץ בבית.</p>
            </div>
            <div className={styles.card}>
              <div className={styles.iconWrapper}><FiMaximize aria-hidden="true" /></div>
              <h3>הסתכלות מערכתית שלמה</h3>
              <p>ראייה רחבה שמחברת בין הייעוץ הזוגי להדרכת ההורים. הבנה עמוקה כיצד הקשר הזוגי משפיע על ההורות, ולהפך, לבניית משפחה חזקה ויציבה.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default TrustSection;
