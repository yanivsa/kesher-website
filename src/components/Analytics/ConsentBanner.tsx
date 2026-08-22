import React, { useEffect, useState } from 'react';
import styles from './ConsentBanner.module.css';

const CONSENT_STORAGE_KEY = 'kesher_consent_v2';
const CONSENT_REGION_ENDPOINT = '/api/consent-region';
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
  const [state, setState] = useState<{ choice: ConsentChoice | null; isOpen: boolean }>(() => ({
    choice: readStoredChoice(),
    isOpen: false,
  }));
  const [requiresConsent, setRequiresConsent] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;

    fetch(CONSENT_REGION_ENDPOINT, {
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Consent region lookup failed');
        const payload = await response.json() as { requiresConsent?: unknown };
        if (typeof payload.requiresConsent !== 'boolean') {
          throw new Error('Invalid consent region response');
        }
        if (active) setRequiresConsent(payload.requiresConsent);
      })
      .catch(() => {
        // Fail closed: if geolocation is unavailable, keep the consent prompt.
        if (active) setRequiresConsent(true);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (state.choice) updateGoogleConsent(state.choice);
  }, [state.choice]);

  useEffect(() => {
    if (requiresConsent === true && state.choice === null && !state.isOpen) {
      setState((current) => ({ ...current, isOpen: true }));
    }
  }, [requiresConsent, state.choice, state.isOpen]);

  const choose = (nextChoice: ConsentChoice) => {
    persistChoice(nextChoice);
    setState({ choice: nextChoice, isOpen: false });

    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'privacy_consent_update',
      consent_choice: nextChoice,
    });
  };

  // Visitors outside the EEA/UK/Switzerland should not be interrupted by a
  // consent banner. The regional defaults in analytics-bootstrap.js preserve
  // measurement there. Existing explicit choices are still honored by GTM.
  if (requiresConsent === false || requiresConsent === null) return null;

  if (!state.isOpen) {
    return (
      <button
        type="button"
        className={styles.settingsButton}
        onClick={() => setState((current) => ({ ...current, isOpen: true }))}
        aria-label="פתיחת הגדרות פרטיות ומדידה"
      >
        הגדרות פרטיות
      </button>
    );
  }

  return (
    <aside className={styles.banner} aria-label="העדפות פרטיות ומדידה">
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
      {state.choice && (
        <span className="sr-only">הבחירה הנוכחית: {state.choice === 'granted' ? 'אישור' : 'ללא cookies'}</span>
      )}
    </aside>
  );
};

export default ConsentBanner;
