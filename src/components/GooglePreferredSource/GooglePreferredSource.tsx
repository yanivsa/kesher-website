import React, { useEffect, useRef } from 'react';
import styles from './GooglePreferredSource.module.css';

const GooglePreferredSource: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const fallbackUrl = 'https://www.google.com/preferences/source?q=kesher.saharoni.com';

  useEffect(() => {
    // Check if script is already present on the document
    const scriptId = 'google-preferred-source-script';
    let script = document.getElementById(scriptId) as HTMLScriptElement;

    if (!script) {
      script = document.createElement('script');
      script.id = scriptId;
      script.src = 'https://news.google.com/swg/js/v1/publisher.js';
      script.async = true;
      document.head.appendChild(script);
    }
  }, []);

  return (
    <div className={styles.container} ref={containerRef}>
      <div google-add-preferred-source-btn="" data-lang="he" data-theme="light"></div>
      <noscript>
        <a
          href={fallbackUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.fallbackLink}
        >
          הוסיפו אותנו כמקור מועדף ב-Google
        </a>
      </noscript>
      <div className={styles.jsFallback}>
        <a
          href={fallbackUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.fallbackLink}
        >
          הוסיפו אותנו כמקור מועדף ב-Google
        </a>
      </div>
    </div>
  );
};

export default GooglePreferredSource;
