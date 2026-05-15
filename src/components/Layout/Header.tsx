import React from 'react';
import styles from './Header.module.css';

const Header: React.FC = () => {
  return (
    <header className={styles.header}>
      <div className={`container ${styles.container}`}>
        <div className={styles.logo}>
          <span className={styles.brand}>קשר</span>
          <span className={styles.subtitle}>שירה סהרוני</span>
        </div>
        <nav className={styles.nav}>
          <a href="#about">אודות</a>
          <a href="#services">שירותים</a>
          <a href="#blog">בלוג</a>
          <a href="#contact" className={styles.cta}>קביעת פגישה</a>
        </nav>
      </div>
    </header>
  );
};

export default Header;
