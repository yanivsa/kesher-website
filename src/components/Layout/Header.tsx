import React, { lazy, Suspense, useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { FiMenu, FiSearch, FiX } from 'react-icons/fi';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './Header.module.css';

const GlobalSearch = lazy(() => import('../GlobalSearch/GlobalSearch'));

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
              <span className={styles.subtitle}>ייעוץ זוגי, הנחיית הורים וגישור</span>
            </div>
          </Link>

          {/* Search + Mobile Toggle */}
          <div className={styles.actions}>
            <SearchTrigger onClick={openSearch} />
            <button
              type="button"
              className={styles.menuToggle}
              onClick={toggleMenu}
              aria-label={isMenuOpen ? 'סגירת תפריט' : 'פתיחת תפריט'}
              aria-expanded={isMenuOpen}
              aria-controls="main-navigation"
            >
              {isMenuOpen ? <FiX /> : <FiMenu />}
            </button>
          </div>

          {/* Navigation */}
          <nav id="main-navigation" aria-label="ניווט ראשי" className={`${styles.nav} ${isMenuOpen ? styles.navOpen : ''}`}>
            <Link to="/about" onClick={closeMenu}>אודות</Link>
            <div className={styles.dropdown}>
              <button type="button" className={styles.navLink}>שירותים</button>
              <div className={styles.dropdownContent}>
                <Link to="/services/couples" onClick={closeMenu}>ייעוץ זוגי</Link>
                <Link to="/services/parenting" onClick={closeMenu}>הדרכת הורים</Link>
                <Link to="/services/mediation" onClick={closeMenu}>גישור</Link>
              </div>
            </div>
            <div className={styles.dropdown}>
              <button type="button" className={styles.navLink}>תחומי התמחות</button>
              <div className={styles.dropdownContent}>
                <Link to="/services/gifted-parenting" onClick={closeMenu}>הורים לילדים מחוננים</Link>
                <Link to="/services/parenting" onClick={closeMenu}>הכנה לכיתה א׳</Link>
                <Link to="/services/gifted-parenting#gifted-framework" onClick={closeMenu}>כניסה למסגרת מחוננים</Link>
                <Link to="/services/aliyah-families" onClick={closeMenu}>עולים ותושבים חוזרים</Link>
              </div>
            </div>
            <Link to="/blog" onClick={closeMenu}>בלוג</Link>
            <Link to="/faq" onClick={closeMenu}>שאלות נפוצות</Link>
            <Link to="/contact" className={styles.cta} onClick={closeMenu}>קביעת פגישה</Link>
          </nav>
        </div>
      </header>

      <Suspense fallback={null}>
        {isSearchOpen && <GlobalSearch isOpen={isSearchOpen} onClose={closeSearch} />}
      </Suspense>
    </>
  );
};

const SearchTrigger: React.FC<{ onClick: () => void }> = ({ onClick }) => (
  <button
    type="button"
    className={styles.searchTrigger}
    onClick={onClick}
    aria-label="חיפוש באתר"
    title="חיפוש"
  >
    <FiSearch aria-hidden="true" />
    <span>חיפוש...</span>
  </button>
);

export default Header;
