import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { FiMenu, FiX } from 'react-icons/fi';
import { SITE_CONFIG } from '../../constants/siteConfig';
import GlobalSearch, { SearchTrigger } from '../GlobalSearch/GlobalSearch';
import styles from './Header.module.css';

const Header: React.FC = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  const toggleMenu = () => {
    setIsMenuOpen(!isMenuOpen);
  };

  const closeMenu = () => {
    setIsMenuOpen(false);
  };

  const openSearch = useCallback(() => {
    setIsSearchOpen(true);
    closeMenu();
  }, []);

  const closeSearch = useCallback(() => {
    setIsSearchOpen(false);
  }, []);

  // Ctrl+K / Cmd+K to open search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(prev => !prev);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  return (
    <>
      <header className={styles.header}>
        <div className={`container ${styles.container}`}>
          <Link to="/" className={styles.logoLink} onClick={closeMenu}>
            <div className={styles.logo}>
              <span className={styles.brand}>{SITE_CONFIG.brand}</span>
              <span className={styles.subtitle}>ייעוץ זוגי וגישור</span>
            </div>
          </Link>

          {/* Search + Mobile Toggle */}
          <div className={styles.actions}>
            <SearchTrigger onClick={openSearch} />
            <button type="button" className={styles.menuToggle} onClick={toggleMenu} aria-label="פתיחת תפריט">
              {isMenuOpen ? <FiX /> : <FiMenu />}
            </button>
          </div>

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

      <GlobalSearch isOpen={isSearchOpen} onClose={closeSearch} />
    </>
  );
};

export default Header;
