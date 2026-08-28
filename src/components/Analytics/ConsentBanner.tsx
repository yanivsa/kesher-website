import React, { useEffect, useState } from 'react';
import styles from './ConsentBanner.module.css';

const CONSENT_STORAGE_KEY = 'kesher_consent_v2';
const CONSENT_DISMISSED_SESSION_KEY = 'kesher_consent_dismissed_v1';
type ConsentChoice = 'granted' | 'denied';

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

const updateGoogleConsent = (choice: ConsentChoice) => {
  window.gtag?.('consent', 'update', {
    ad_storage: choice,
    analytics_storage: choice,
    ad_user_data: choice,
    ad_personalization: choice,
  });
};

const readStoredChoice = (): ConsentChoice | null => {
  try {
    const value = window.localStorage.getItem(CONSENT_STORAGE_KEY);
    return value === 'granted' || value === 'denied' ? value : null;
  } catch {
    return null;
  }
};

const wasDismissedThisSession = () => {
  try {
    return window.sessionStorage.getItem(CONSENT_DISMISSED_SESSION_KEY) === 'true';
  } catch {
    return false;
  }
};

const persistChoice = (choice: ConsentChoice) => {
  try {
    window.localStorage.setItem(CONSENT_STORAGE_KEY, choice);
  } catch {
    // Consent still applies for the current page even if persistence is unavailable.
  }
};

const ConsentBanner: React.FC = () => {
  const [state, setState] = useState<{ choice: ConsentChoice | null; isOpen: boolean }>(() => {
    const stored = readStoredChoice();
    return { choice: stored, isOpen: stored === null && !wasDismissedThisSession() };
  });

  useEffect(() => {
    if (state.choice) updateGoogleConsent(state.choice);
  }, [state.choice]);

  const choose = (nextChoice: ConsentChoice) => {
    persistChoice(nextChoice);
    setState({ choice: nextChoice, isOpen: false });

    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'privacy_consent_update',
      consent_choice: nextChoice,
    });
  };

  const dismiss = () => {
    try {
      window.sessionStorage.setItem(CONSENT_DISMISSED_SESSION_KEY, 'true');
    } catch {
      // Dismissal can remain page-local if session storage is unavailable.
    }

    setState((current) => ({ ...current, isOpen: false }));
  };

  if (!state.isOpen) {
    return (
      <button
        type="button"
        className={styles.settingsButton}
        onClick={() => setState((current) => ({ ...current, isOpen: true }))}
        aria-label="פתיחת הגדרות פרטיות ומדידה"
      >
        פרטיות
      </button>
    );
  }

  return (
    <aside className={styles.banner} aria-label="העדפות פרטיות ומדידה">
      <p>
        באתר נעשה שימוש בקובצי Cookies ובכלי המדידה של Google לצורך סטטיסטיקה, שיפור חוויית הגלישה ומדידת יעילות הפרסום.{' '}
        <a href="/privacy#cookies-measurement">מידע נוסף</a>
      </p>
      <div className={styles.actions}>
        <button
          type="button"
          className={styles.accept}
          onClick={() => choose('granted')}
          aria-label="אישור מדידה"
        >
          אישור
        </button>
        <button
          type="button"
          className={styles.reject}
          onClick={() => choose('denied')}
          aria-label="המשך ללא cookies"
        >
          ללא Cookies
        </button>
      </div>
      <button
        type="button"
        className={styles.closeButton}
        onClick={dismiss}
        aria-label="סגירה והשארת cookies לא-חיוניים חסומים"
        title="סגירה"
      >
        ×
      </button>
      {state.choice && (
        <span className="sr-only">הבחירה הנוכחית: {state.choice === 'granted' ? 'אישור' : 'ללא cookies'}</span>
      )}
    </aside>
  );
};

export default ConsentBanner;
