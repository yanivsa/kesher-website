import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { FiMenu, FiSearch, FiX } from 'react-icons/fi';
import { SITE_CONFIG } from '../../constants/siteConfig';
import GlobalSearch from '../GlobalSearch/GlobalSearch';
import styles from './Header.module.css';

const Header: React.FC = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const menuCloseRef = useRef<HTMLButtonElement>(null);
  const navRef = useRef<HTMLElement>(null);
  const searchButtonRef = useRef<HTMLButtonElement>(null);

  const toggleMenu = () => {
    setIsMenuOpen((open) => !open);
  };

  const closeMenu = useCallback(() => {
    setIsMenuOpen(false);
  }, []);

  const dismissMenu = useCallback(() => {
    closeMenu();
    window.requestAnimationFrame(() => menuButtonRef.current?.focus());
  }, [closeMenu]);

  const openSearch = useCallback(() => {
    setIsSearchOpen(true);
    closeMenu();
  }, [closeMenu]);

  const closeSearch = useCallback(() => {
    setIsSearchOpen(false);
    window.requestAnimationFrame(() => searchButtonRef.current?.focus());
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

  useEffect(() => {
    if (!isMenuOpen) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    menuCloseRef.current?.focus();

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') dismissMenu();
      if (event.key !== 'Tab' || !navRef.current) return;

      const focusable = Array.from(
        navRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), a[href]'),
      ).filter((element) => element.offsetParent !== null);
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleEscape);
    };
  }, [dismissMenu, isMenuOpen]);

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
            <SearchTrigger ref={searchButtonRef} onClick={openSearch} />
            {!isMenuOpen && (
              <button
                ref={menuButtonRef}
                type="button"
                className={styles.menuToggle}
                onClick={toggleMenu}
                aria-label="פתיחת תפריט"
                aria-expanded="false"
                aria-controls="main-navigation"
              >
                <FiMenu aria-hidden="true" />
              </button>
            )}
          </div>

          {isMenuOpen && (
            <button
              type="button"
              className={styles.menuBackdrop}
              onClick={dismissMenu}
              aria-label="סגירת התפריט בלחיצה מחוץ לתפריט"
            />
          )}

          {/* Navigation */}
          <nav ref={navRef} id="main-navigation" aria-label="ניווט ראשי" className={`${styles.nav} ${isMenuOpen ? styles.navOpen : ''}`}>
            <div className={styles.mobileMenuHeader}>
              <span>תפריט</span>
              <button
                ref={menuCloseRef}
                type="button"
                className={styles.menuClose}
                onClick={dismissMenu}
                aria-label="סגירת תפריט"
                aria-expanded="true"
                aria-controls="main-navigation"
              >
                <FiX aria-hidden="true" />
              </button>
            </div>
            <Link to="/about" onClick={closeMenu}>אודות</Link>
            <div className={styles.dropdown}>
              <button type="button" className={styles.navLink}>שירותים</button>
              <div className={styles.dropdownContent}>
                <Link to="/services/couples" onClick={closeMenu}>ייעוץ זוגי</Link>
                <Link to="/services/late-singleness" onClick={closeMenu}>ייעוץ ברווקות מאוחרת</Link>
                <Link to="/services/finding-relationship" onClick={closeMenu}>ליווי למציאת זוגיות</Link>
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
            <Link to={SITE_CONFIG.links.appointment} className={styles.cta} onClick={closeMenu}>קביעת פגישה</Link>
          </nav>
        </div>
      </header>

      {isSearchOpen && <GlobalSearch isOpen={isSearchOpen} onClose={closeSearch} />}
    </>
  );
};

const SearchTrigger = React.forwardRef<HTMLButtonElement, { onClick: () => void }>(({ onClick }, ref) => (
  <button
    ref={ref}
    type="button"
    className={styles.searchTrigger}
    onClick={onClick}
    aria-label="חיפוש באתר"
    title="חיפוש"
  >
    <FiSearch aria-hidden="true" />
    <span>חיפוש...</span>
  </button>
));

SearchTrigger.displayName = 'SearchTrigger';

export default Header;
