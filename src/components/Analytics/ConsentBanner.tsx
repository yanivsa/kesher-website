import React, { useEffect, useState } from 'react';
import styles from './ConsentBanner.module.css';

const CONSENT_STORAGE_KEY = 'kesher_consent_v2';
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
    return { choice: stored, isOpen: stored === null };
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
        האתר משתמש בכלי Google למדידת שימוש ופרסום. אפשר לאשר cookies או להמשיך בלעדיהם.{' '}
        <a href="/privacy">מדיניות פרטיות</a>.
      </p>
      <div className={styles.actions}>
        <button type="button" className={styles.accept} onClick={() => choose('granted')}>
          אישור מדידה
        </button>
        <button type="button" className={styles.reject} onClick={() => choose('denied')}>
          ללא cookies
        </button>
      </div>
      {state.choice && (
        <span className="sr-only">הבחירה הנוכחית: {state.choice === 'granted' ? 'אישור' : 'ללא cookies'}</span>
      )}
    </aside>
  );
};

export default ConsentBanner;
