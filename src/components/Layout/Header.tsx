import React from 'react';
import { Link } from 'react-router-dom';
import styles from './Header.module.css';

const Header: React.FC = () => {
  return (
    <header className={styles.header}>
      <div className={`container ${styles.container}`}>
        <Link to="/" className={styles.logoLink}>
          <div className={styles.logo}>
            <span className={styles.brand}>קשר</span>
            <span className={styles.subtitle}>שירה סהרוני</span>
          </div>
        </Link>
        <nav className={styles.nav}>
          <Link to="/#about">אודות</Link>
          <div className={styles.dropdown}>
            <span className={styles.navLink}>שירותים</span>
            <div className={styles.dropdownContent}>
              <Link to="/services/couples">ייעוץ זוגי</Link>
              <Link to="/services/parenting">הדרכת הורים</Link>
              <Link to="/services/mediation">גישור משפחתי</Link>
            </div>
          </div>
          <Link to="/#blog">בלוג</Link>
          <a href="/#contact" className={styles.cta}>קביעת פגישה</a>
        </nav>
      </div>
    </header>
  );
};

export default Header;
