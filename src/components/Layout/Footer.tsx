import React from 'react';
import { Link } from 'react-router-dom';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './Footer.module.css';

const Footer: React.FC = () => {
  return (
    <footer className={styles.footer}>
      <div className={`container ${styles.container}`}>
        <div className={styles.info}>
          <div className={styles.logo}>
            <span className={styles.brand}>{SITE_CONFIG.brand}</span>
            <span className={styles.subtitle}>ייעוץ זוגי והנחיית הורים</span>
          </div>
          <p>יועצת זוגית ומנחת הורים.</p>
        </div>
        <div className={styles.links}>
          <h4>ניווט מהיר</h4>
          <Link to="/">דף הבית</Link>
          <Link to="/about">אודות</Link>
          <Link to="/services/premarital-first-year">הכנה לנישואים והשנה הראשונה</Link>
          <Link to="/services/couples-aliyah-relocation">זוגיות בעלייה וברילוקיישן</Link>
          <Link to="/services/late-singleness">ייעוץ ברווקות מאוחרת</Link>
          <Link to="/services/finding-relationship">ליווי למציאת זוגיות</Link>
          <Link to="/services/gifted-parenting">הורים לילדים מחוננים</Link>
          <Link to="/services/aliyah-families">עולים ותושבים חוזרים</Link>
          <Link to="/faq">שאלות נפוצות</Link>
          <Link to={SITE_CONFIG.links.appointment}>קביעת פגישה</Link>
          <Link to="/contact">צור קשר</Link>
        </div>
        <div className={styles.contact}>
          <h4>פרטי התקשרות</h4>
          <p>{`טלפון: ${SITE_CONFIG.contact.phone}`}</p>
          <p>{`אימייל: ${SITE_CONFIG.contact.email}`}</p>
          <p>{`מיקום: ${SITE_CONFIG.contact.location}`}</p>
        </div>
        <div className={styles.legal}>
          <h4>מידע</h4>
          <Link to="/accessibility">הצהרת נגישות</Link>
          <Link to="/privacy">מדיניות פרטיות</Link>
          <Link to="/terms">תנאי שימוש</Link>
        </div>
      </div>
      <div className={styles.bottom}>
        <div className="container">
          <p>{`© ${new Date().getFullYear()} ${SITE_CONFIG.brand}. כל הזכויות שמורות.`}</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
