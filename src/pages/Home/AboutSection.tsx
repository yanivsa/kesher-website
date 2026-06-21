import React from 'react';
import { FiAward, FiCompass, FiBookOpen } from 'react-icons/fi';
import styles from './AboutSection.module.css';

const AboutSection: React.FC = () => {
  return (
    <section id="about" className={styles.about}>
      <div className={`container ${styles.container}`}>
        <div className={styles.imageContainer}>
          <div className={styles.imageWrapper}>
            <img 
              src="/images/generated/site/about-office.png" 
              alt="קליניקה נעימה ומזמינה" 
              className={styles.aboutImage}
              width="1024"
              height="1024"
              loading="lazy"
            />
            <div className={styles.experienceBadge}>
              <span className={styles.years}>בעלת</span>
              <span className={styles.yearsText}>ניסיון מקצועי</span>
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
              השילוב בין ייעוץ זוגי והנחיית הורים מאפשר לי להסתכל על המשפחה כמערכת אחת: הקשר הזוגי, ההורות והילדים.
            </p>
          </div>
          <div className={styles.credentials}>
            <div className={styles.credential}>
              <span className={styles.icon}><FiCompass aria-hidden="true" /></span>
              <span>ליווי זוגות סביב אתגרי תקשורת, קשיי קירבה והגעה להבנות</span>
            </div>
            <div className={styles.credential}>
              <span className={styles.icon}><FiAward aria-hidden="true" /></span>
              <span>הדרכת הורים, כולל התמודדות עם ADHD ואתגרי קשב</span>
            </div>
            <div className={styles.credential}>
              <span className={styles.icon}><FiBookOpen aria-hidden="true" /></span>
              <span>הכשרה מקצועית מקיפה בתחומי הייעוץ הזוגי והדרכת ההורים</span>
            </div>
          </div>
          <a href="#contact" className={styles.cta}>בואו נדבר</a>
        </div>
      </div>
    </section>
  );
};

export default AboutSection;
