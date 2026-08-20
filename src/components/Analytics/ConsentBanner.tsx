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
  const [choice, setChoice] = useState<ConsentChoice | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const stored = readStoredChoice();
    setChoice(stored);
    setIsOpen(stored === null);
    if (stored) updateGoogleConsent(stored);
  }, []);

  const choose = (nextChoice: ConsentChoice) => {
    persistChoice(nextChoice);
    updateGoogleConsent(nextChoice);
    setChoice(nextChoice);
    setIsOpen(false);

    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'privacy_consent_update',
      consent_choice: nextChoice,
    });
  };

  if (!isOpen) {
    return (
      <button
        type="button"
        className={styles.settingsButton}
        onClick={() => setIsOpen(true)}
        aria-label="פתיחת הגדרות פרטיות ומדידה"
      >
        הגדרות פרטיות
      </button>
    );
  }

  return (
    <aside className={styles.banner} role="dialog" aria-label="העדפות פרטיות ומדידה">
      <p>
        האתר משתמש בכלי מדידה של Google כדי להבין ביצועים של פרסום ושימוש באתר.
        ניתן לאשר מדידה מבוססת cookies או להמשיך ללא cookies.{' '}
        <a href="/privacy">למדיניות הפרטיות</a>.
      </p>
      <div className={styles.actions}>
        <button type="button" className={styles.accept} onClick={() => choose('granted')}>
          אישור מדידה
        </button>
        <button type="button" className={styles.reject} onClick={() => choose('denied')}>
          המשך ללא cookies
        </button>
      </div>
      {choice && (
        <span className="sr-only">הבחירה הנוכחית: {choice === 'granted' ? 'אישור' : 'ללא cookies'}</span>
      )}
    </aside>
  );
};

export default ConsentBanner;
