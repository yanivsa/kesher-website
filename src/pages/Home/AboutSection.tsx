import React from 'react';
import { FiAward, FiCompass, FiBookOpen } from 'react-icons/fi';
import { Link } from 'react-router-dom';
import SignatureMark from '../../components/Signature/SignatureMark';
import styles from './AboutSection.module.css';

const AboutSection: React.FC = () => {
  return (
    <section id="about" className={styles.about}>
      <div className={`container ${styles.container}`}>
        <div className={styles.imageContainer}>
          <div className={styles.imageWrapper}>
            <img
              src="/images/shira-saharoni.webp"
              alt="שירה סהרוני, יועצת זוגית ומשפחתית, מגשרת ומנחת הורים"
              className={styles.aboutImage}
              width="1271"
              height="1280"
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
            עורכת דין בהכשרתי ומגשרת מוסמכת, שבחרה לעבור מעולם המשפט לעולמות ההנחיה, הייעוץ והחינוך.
          </p>
          <div className={styles.description}>
            <p>
              אני אוהבת לפרק יחד מצב שנראה מסובך: להבין מי נפגע, מה חוזר על עצמו ומה אפשר לנסות אחרת כבר השבוע. לפעמים המוקד הוא הזוגיות, לפעמים ההורות, ולעיתים אי אפשר באמת להפריד ביניהן.
            </p>
          </div>
          <div className={styles.credentials}>
            <div className={styles.credential}>
              <span className={styles.icon}><FiCompass aria-hidden="true" /></span>
              <span>ייעוץ זוגי וגישור סביב תקשורת, קירבה ובניית הסכמות</span>
            </div>
            <div className={styles.credential}>
              <span className={styles.icon}><FiAward aria-hidden="true" /></span>
              <span>הנחיית הורים לילדים מחוננים ולילדים עם ADHD ואתגרי קשב</span>
            </div>
            <div className={styles.credential}>
              <span className={styles.icon}><FiBookOpen aria-hidden="true" /></span>
              <span>ליווי משפחות במעברים חינוכיים, בעלייה ובחזרה לישראל</span>
            </div>
          </div>
          <SignatureMark tone="about" animated className={styles.signature} />
          <Link to="/about" className={styles.cta}>עוד עליי ועל אופן העבודה</Link>
        </div>
      </div>
    </section>
  );
};

export default AboutSection;
