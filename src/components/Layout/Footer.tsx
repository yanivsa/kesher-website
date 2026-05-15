import React from 'react';
import styles from './Footer.module.css';

const Footer: React.FC = () => {
  return (
    <footer className={styles.footer}>
      <div className={`container ${styles.container}`}>
        <div className={styles.info}>
          <div className={styles.logo}>
            <span className={styles.brand}>קשר</span>
            <span className={styles.subtitle}>שירה סהרוני</span>
          </div>
          <p>יועצת זוגית, מנחת הורים ומגשרת מוסמכת.</p>
        </div>
        <div className={styles.links}>
          <h4>ניווט מהיר</h4>
          <a href="/">דף הבית</a>
          <a href="#about">אודות</a>
          <a href="#services">שירותים</a>
          <a href="#contact">צור קשר</a>
        </div>
        <div className={styles.contact}>
          <h4>פרטי התקשרות</h4>
          <p>טלפון: 05X-XXXXXXX</p>
          <p>אימייל: shira@example.com</p>
          <p>מיקום: אשדוד / אונליין</p>
        </div>
      </div>
      <div className={styles.bottom}>
        <div className="container">
          <p>© {new Date().getFullYear()} קשר - שירה סהרוני. כל הזכויות שמורות.</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
