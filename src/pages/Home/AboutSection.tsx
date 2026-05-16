import React from 'react';
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
            אני מאמינה שמערכות יחסים הן הלב הפועם של החיים שלנו, וכשהן במיטבן – אנחנו במיטבנו.
          </p>
          <div className={styles.description}>
            <p>
              כעורכת דין ומגשרת מוסמכת, לצד היותי יועצת זוגית ומנחת הורים, אני מביאה לקליניקה שילוב ייחודי של הבנה משפטית עמוקה וראייה טיפולית רגישה.
            </p>
            <p>
              הגישה שלי משלבת כלים מעולם ה-Gottman וה-EFT יחד עם פרקטיקה של תקשורת מקרבת. אני עוזרת לזוגות ולמשפחות למצוא את הדרך חזרה אחד לשני, גם ברגעים שנראים בלתי אפשריים.
            </p>
          </div>
          <div className={styles.credentials}>
            <div className={styles.credential}>
              <span className={styles.icon}>🎓</span>
              <span>עורכת דין ומגשרת מוסמכת</span>
            </div>
            <div className={styles.credential}>
              <span className={styles.icon}>🤝</span>
              <span>מומחית בגישור וגירושין בשיתוף פעולה</span>
            </div>
            <div className={styles.credential}>
              <span className={styles.icon}>🌟</span>
              <span>מומחית בהדרכת הורים לילדים עם ADHD</span>
            </div>
          </div>
          <a href="#contact" className={styles.cta}>בואו נדבר</a>
        </div>
      </div>
    </section>
  );
};

export default AboutSection;
