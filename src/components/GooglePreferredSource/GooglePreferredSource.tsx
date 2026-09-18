import React, { useEffect, useRef } from 'react';
import styles from './GooglePreferredSource.module.css';

type PreferredSourceApi = {
  init: (options: { theme: 'light' | 'dark'; lang?: string }) => void;
  addPreferredSource: () => void;
};

type PreferredSourceWindow = Window & {
  PREFERRED_SOURCE?: Array<(preferredSource: PreferredSourceApi) => void>;
};

const SCRIPT_ID = 'google-preferred-source-script';
const SCRIPT_SRC = 'https://news.google.com/swg/js/v1/publisher.js';
const FALLBACK_URL = 'https://www.google.com/preferences/source?q=kesher.saharoni.com';

const GooglePreferredSource: React.FC = () => {
  const apiRef = useRef<PreferredSourceApi | null>(null);

  useEffect(() => {
    const preferredWindow = window as PreferredSourceWindow;
    preferredWindow.PREFERRED_SOURCE = preferredWindow.PREFERRED_SOURCE || [];
    preferredWindow.PREFERRED_SOURCE.push((preferredSource) => {
      preferredSource.init({ theme: 'light', lang: 'he' });
      apiRef.current = preferredSource;
    });

    let script = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
    if (!script) {
      script = document.createElement('script');
      script.id = SCRIPT_ID;
      script.src = SCRIPT_SRC;
      script.async = true;
      script.setAttribute('preferred-sources-control', 'manual');
      document.head.appendChild(script);
    }
  }, []);

  const handlePreferredSource = () => {
    if (apiRef.current) {
      apiRef.current.addPreferredSource();
      return;
    }

    window.open(FALLBACK_URL, '_blank', 'noopener,noreferrer');
  };

  return (
    <section className={styles.container} aria-label="הוספה למקורות המועדפים ב-Google">
      <p className={styles.label}>רוצים למצוא את המאמרים של שירה בקלות גם ב-Google?</p>
      <button type="button" className={styles.button} onClick={handlePreferredSource}>
        הוסיפו את שירה למקורות המועדפים
      </button>
      <noscript>
        <a
          href={FALLBACK_URL}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.fallbackLink}
        >
          הוסיפו את שירה למקורות המועדפים ב-Google
        </a>
      </noscript>
    </section>
  );
};

export default GooglePreferredSource;
