import React from 'react';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './Footer.module.css';

const Footer: React.FC = () => {
  return (
    <footer className={styles.footer}>
      <div className={`container ${styles.container}`}>
        <div className={styles.info}>
          <div className={styles.logo}>
            <span className={styles.brand}>{SITE_CONFIG.brand}</span>
            <span className={styles.subtitle}>{SITE_CONFIG.author}</span>
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
          <p>טלפון: {SITE_CONFIG.contact.phone}</p>
          <p>אימייל: {SITE_CONFIG.contact.email}</p>
          <p>מיקום: {SITE_CONFIG.contact.location}</p>
        </div>
      </div>
      <div className={styles.bottom}>
        <div className="container">
          <p>© {new Date().getFullYear()} {SITE_CONFIG.brand} - {SITE_CONFIG.author}. כל הזכויות שמורות.</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
