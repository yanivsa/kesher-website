import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { FiMenu, FiX } from 'react-icons/fi';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './Header.module.css';

const Header: React.FC = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const toggleMenu = () => {
    setIsMenuOpen(!isMenuOpen);
  };

  const closeMenu = () => {
    setIsMenuOpen(false);
  };

  return (
    <header className={styles.header}>
      <div className={`container ${styles.container}`}>
        <Link to="/" className={styles.logoLink} onClick={closeMenu}>
          <div className={styles.logo}>
            <span className={styles.brand}>{SITE_CONFIG.brand}</span>
            <span className={styles.subtitle}>ייעוץ זוגי וגישור</span>
          </div>
        </Link>

        {/* Mobile Toggle Button */}
        <button className={styles.menuToggle} onClick={toggleMenu} aria-label="פתיחת תפריט">
          {isMenuOpen ? <FiX /> : <FiMenu />}
        </button>

        {/* Navigation */}
        <nav className={`${styles.nav} ${isMenuOpen ? styles.navOpen : ''}`}>
          <Link to="/about" onClick={closeMenu}>אודות</Link>
          <div className={styles.dropdown}>
            <span className={styles.navLink}>שירותים</span>
            <div className={styles.dropdownContent}>
              <Link to="/services/couples" onClick={closeMenu}>ייעוץ זוגי</Link>
              <Link to="/services/parenting" onClick={closeMenu}>הדרכת הורים</Link>
              <Link to="/services/mediation" onClick={closeMenu}>גישור משפחתי</Link>
            </div>
          </div>
          <Link to="/blog" onClick={closeMenu}>בלוג</Link>
          <Link to="/faq" onClick={closeMenu}>שאלות נפוצות</Link>
          <Link to="/contact" className={styles.cta} onClick={closeMenu}>קביעת פגישה</Link>
        </nav>
      </div>
    </header>
  );
};

export default Header;
