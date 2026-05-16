import React from 'react';
import { FiAward, FiBriefcase, FiCompass } from 'react-icons/fi';
import styles from './AboutSection.module.css';

const AboutSection: React.FC = () => {
  return (
    <section id="about" className={styles.about}>
      <div className={`container ${styles.container}`}>
        <div className={styles.imageContainer}>
          <div className={styles.imageWrapper}>
            <img 
              src="https://images.unsplash.com/photo-1521791136064-7986c2920216?auto=format&fit=crop&w=1200&q=80" 
              alt="קליניקה נעימה ומזמינה" 
              className={styles.aboutImage}
            />
            <div className={styles.experienceBadge}>
              <span className={styles.years}>15+</span>
              <span className={styles.yearsText}>שנות ניסיון</span>
            </div>
          </div>
        </div>
        <div className={styles.content}>
          <h2 className={styles.title}>נעים מאוד, שירה סהרוני</h2>
          <p className={styles.lead}>
            אני פוגשת זוגות, הורים ומשפחות ברגעים שבהם השיחה כבר לא מצליחה להחזיק את המורכבות לבד.
          </p>
          <div className={styles.description}>
            <p>
              השילוב בין ייעוץ זוגי, הנחיית הורים וגישור מאפשר לי להסתכל על המשפחה כמערכת אחת: הקשר הזוגי, ההורות, הילדים וההחלטות המעשיות שצריך לקבל.
            </p>
            <p>
              הרקע המשפטי והגישורי מוסיף לתהליך חשיבה מובנית, דיסקרטיות ויכולת להחזיק גם שיחות טעונות בלי להפוך אותן למאבק. המטרה היא לאפשר שיחה ברורה, מכבדת וישימה.
            </p>
          </div>
          <div className={styles.credentials}>
            <div className={styles.credential}>
              <span className={styles.icon}><FiBriefcase aria-hidden="true" /></span>
              <span>עורכת דין ומגשרת מוסמכת</span>
            </div>
            <div className={styles.credential}>
              <span className={styles.icon}><FiCompass aria-hidden="true" /></span>
              <span>ליווי זוגות ומשפחות סביב קונפליקט, פרידה והסכמות</span>
            </div>
            <div className={styles.credential}>
              <span className={styles.icon}><FiAward aria-hidden="true" /></span>
              <span>הדרכת הורים, כולל התמודדות עם ADHD ואתגרי קשב</span>
            </div>
          </div>
          <a href="#contact" className={styles.cta}>בואו נדבר</a>
        </div>
      </div>
    </section>
  );
};

export default AboutSection;
