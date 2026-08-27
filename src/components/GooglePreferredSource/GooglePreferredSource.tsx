import React, { useEffect, useRef } from 'react';
import styles from './GooglePreferredSource.module.css';

const GooglePreferredSource: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const fallbackUrl = 'https://www.google.com/preferences/source?q=kesher.saharoni.com';

  useEffect(() => {
    // Check if script is already present on the document
    const scriptId = 'google-preferred-source-script';
    let script = document.getElementById(scriptId) as HTMLScriptElement;

    const initWidget = () => {
      // @ts-expect-error - Google Preferred Source API
      if (window.preferredSource && typeof window.preferredSource.ready === 'function') {
        // @ts-expect-error - Google Preferred Source API
        window.preferredSource.ready().then((api) => {
          if (api && typeof api.init === 'function') {
            api.init();
          }
        });
      }
    };

    if (!script) {
      script = document.createElement('script');
      script.id = scriptId;
      script.src = 'https://news.google.com/swg/js/v1/publisher.js';
      script.async = true;
      script.setAttribute('preferred-sources-control', 'manual');
      script.onload = initWidget;
      document.body.appendChild(script);
    } else {
      initWidget();
    }

  }, []);

  return (
    <div className={styles.container} ref={containerRef}>
      <google-add-preferred-source-btn data-lang="he" data-theme="light"></google-add-preferred-source-btn>
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
      <div className={styles.jsFallback} aria-hidden="true" tabIndex={-1}>
        <a
          href={fallbackUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.fallbackLink}
          tabIndex={-1}
        >
          הוסיפו אותנו כמקור מועדף ב-Google
        </a>
      </div>
    </div>
  );
};

export default GooglePreferredSource;
