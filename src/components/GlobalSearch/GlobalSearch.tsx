import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FiSearch, FiFileText, FiHelpCircle, FiBriefcase, FiInfo } from 'react-icons/fi';
import Fuse from 'fuse.js';
import { searchIndex, type SearchItem } from '../../data/searchIndex';
import styles from './GlobalSearch.module.css';

const typeLabels: Record<SearchItem['type'], string> = {
  blog: 'מאמר',
  faq: 'שאלה נפוצה',
  service: 'שירות',
  page: 'דף',
};

const typeIcons: Record<SearchItem['type'], React.ReactNode> = {
  blog: <FiFileText />,
  faq: <FiHelpCircle />,
  service: <FiBriefcase />,
  page: <FiInfo />,
};

const iconClass: Record<SearchItem['type'], string> = {
  blog: styles.iconBlog,
  faq: styles.iconFaq,
  service: styles.iconService,
  page: styles.iconPage,
};

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

const GlobalSearch: React.FC<Props> = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const fuse = useMemo(() => new Fuse(searchIndex, {
    keys: [
      { name: 'title', weight: 2 },
      { name: 'body', weight: 1 },
    ],
    threshold: 0.35,
    minMatchCharLength: 2,
  }), []);

  const results = useMemo(() => {
    if (!query.trim()) return [];
    return fuse.search(query, { limit: 8 }).map(r => r.item);
  }, [query, fuse]);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen) {
      // Use requestAnimationFrame to ensure the DOM has updated
      // and the input is visible before trying to focus it
      requestAnimationFrame(() => {
        requestAnimationFrame(() => inputRef.current?.focus());
      });
    }
  }, [isOpen]);

  // Close on Escape
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose();
    if (e.key === 'Tab' && modalRef.current) {
      const focusable = Array.from(
        modalRef.current.querySelectorAll<HTMLElement>('button, a[href], input, [tabindex]:not([tabindex="-1"])'),
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }, [onClose]);

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, handleKeyDown]);

  // Ctrl+K global shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (isOpen) onClose();
        // parent handles opening
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  const handleResultClick = (url: string) => {
    onClose();
    navigate(url);
  };

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        ref={modalRef}
        className={styles.modal}
        onClick={e => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="חיפוש באתר"
      >
        {/* Input */}
        <div className={styles.inputWrapper}>
          <FiSearch className={styles.searchIcon} />
          <input
            ref={inputRef}
            type="text"
            className={styles.input}
            placeholder="חיפוש מאמרים, שאלות, שירותים..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            aria-label="חיפוש באתר"
          />
          <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="סגירת חיפוש">
            ESC
          </button>
        </div>

        {/* Results */}
        <div className={styles.results} aria-live="polite">
          {query.trim() && results.length === 0 && (
            <div className={styles.empty}>
              <div className={styles.emptyIcon}>🔍</div>
              <div className={styles.emptyTitle}>לא נמצאו תוצאות</div>
              <div className={styles.emptyText}>נסו מילות חיפוש אחרות</div>
            </div>
          )}

          {!query.trim() && (
            <div className={styles.empty}>
              <div className={styles.emptyIcon}>✨</div>
              <div className={styles.emptyTitle}>חיפוש באתר</div>
              <div className={styles.emptyText}>הקלידו כדי לחפש בכל המאמרים, השאלות הנפוצות והשירותים</div>
            </div>
          )}

          {results.map(item => (
            <Link
              key={item.id}
              to={item.url}
              className={styles.resultLink}
              onClick={(e) => { e.preventDefault(); handleResultClick(item.url); }}
            >
              <span className={`${styles.iconCol} ${iconClass[item.type]}`}>
                {typeIcons[item.type]}
              </span>
              <span className={styles.textCol}>
                <span className={styles.resultTitle}>{item.title}</span>
                <span className={styles.resultBody}>{item.body}</span>
              </span>
              <span className={styles.badge}>{typeLabels[item.type]}</span>
            </Link>
          ))}
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <span><kbd className={styles.footerKbd}>↵</kbd> לפתיחה</span>
          <span><kbd className={styles.footerKbd}>ESC</kbd> לסגירה</span>
        </div>
      </div>
    </div>
  );
};

export default GlobalSearch;
