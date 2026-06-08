import React from 'react';
import { FiAward, FiShield, FiHeart } from 'react-icons/fi';
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
            הליווי המקצועי משלב ידע אקדמי ומעשי משלושה עולמות תוכן משלימים, כדי לתת לכם מענה מקיף, בטוח ומדויק.
          </p>
          <div className={`${styles.grid} reveal-stagger ${isVisible ? 'visible' : ''}`}>
            <div className={styles.card}>
              <div className={styles.iconWrapper}><FiHeart aria-hidden="true" /></div>
              <h3>ייעוץ זוגי והדרכת הורים</h3>
              <p>הסמכה מקצועית בייעוץ זוגי והנחיית משפחות. התמקדות בשיפור התקשורת, ויסות רגשי ויצירת קרבה אמיתית.</p>
            </div>
            <div className={styles.card}>
              <div className={styles.iconWrapper}><FiShield aria-hidden="true" /></div>
              <h3>גישור משפחתי</h3>
              <p>מגשרת מוסמכת מטעם לשכת עורכי הדין. מומחיות בבניית הסכמות רגישות למשפחות במשבר ומעברי חיים.</p>
            </div>
            <div className={styles.card}>
              <div className={styles.iconWrapper}><FiAward aria-hidden="true" /></div>
              <h3>רקע משפטי</h3>
              <p>כעורכת דין (LL.B), הגישור מנוהל תוך הבנה עמוקה של המשמעויות המעשיות, מה שמעניק לכם ביטחון ושקט נפשי בהחלטות שמתקבלות.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default TrustSection;
