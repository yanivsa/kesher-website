import React, { useEffect, useRef, useState } from 'react';
import { SITE_CONFIG } from '../../constants/siteConfig';
import {
  getAttributionDataLayerFields,
  getCalendlyUtm,
  getStoredAttribution,
} from '../../lib/attribution';
import styles from './CalendlyBookingEmbed.module.css';

const CALENDLY_WIDGET_SRC = 'https://assets.calendly.com/assets/external/widget.js';
const CALENDLY_ORIGIN = 'https://calendly.com';
const AUTO_RESIZE_ACTIVE_ATTRIBUTE = 'data-kesher-calendly-auto-resize';

type CalendlyApi = {
  initInlineWidget: (options: {
    url: string;
    parentElement: HTMLElement;
    resize: boolean;
    utm?: {
      utmSource?: string;
      utmMedium?: string;
      utmCampaign?: string;
      utmContent?: string;
      utmTerm?: string;
    };
  }) => void;
};

type WindowWithCalendly = Window & {
  Calendly?: CalendlyApi;
};

type CalendlyMessagePayload = {
  event?: { uri?: string };
  invitee?: { uri?: string };
};

type CalendlyMessage = {
  event?: string;
  payload?: CalendlyMessagePayload;
};

export type CalendlyBookingEmbedProps = {
  ariaLabel: string;
  serviceType: string;
  bookingPagePath?: string;
  landingPageType?: string;
  variantId?: string;
  value?: number;
  currency?: string;
  redirectTo?: string;
  redirectOnBooked?: boolean;
  className?: string;
};

let calendlyScriptPromise: Promise<void> | null = null;

const loadCalendlyScript = (): Promise<void> => {
  if (typeof window === 'undefined') return Promise.resolve();
  if ((window as WindowWithCalendly).Calendly) return Promise.resolve();
  if (calendlyScriptPromise) return calendlyScriptPromise;

  calendlyScriptPromise = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${CALENDLY_WIDGET_SRC}"]`,
    );

    const handleLoad = () => {
      if ((window as WindowWithCalendly).Calendly) {
        resolve();
      } else {
        reject(new Error('Calendly script loaded without exposing its API.'));
      }
    };

    const handleError = () => reject(new Error('Calendly script failed to load.'));

    if (existing) {
      existing.addEventListener('load', handleLoad, { once: true });
      existing.addEventListener('error', handleError, { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = CALENDLY_WIDGET_SRC;
    script.async = true;
    script.addEventListener('load', handleLoad, { once: true });
    script.addEventListener('error', handleError, { once: true });
    document.head.appendChild(script);
  }).catch((error) => {
    calendlyScriptPromise = null;
    throw error;
  });

  return calendlyScriptPromise;
};

const safeSessionGet = (key: string): string | null => {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
};

const safeSessionSet = (key: string, value: string) => {
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    // Conversion tracking must not break booking when storage is unavailable.
  }
};

const sendBrowserBookingConfirmation = async (payload: Record<string, unknown>) => {
  try {
    await fetch('/api/booking/browser-confirmation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'same-origin',
      keepalive: true,
    });
  } catch {
    // Server reconciliation is a secondary safety channel. Never block conversion/UX.
  }
};

const CalendlyBookingEmbed: React.FC<CalendlyBookingEmbedProps> = ({
  ariaLabel,
  serviceType,
  bookingPagePath,
  landingPageType,
  variantId,
  value,
  currency = 'ILS',
  redirectTo = '/thank-you-booked',
  redirectOnBooked = true,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    let disposed = false;
    let redirectTimer: number | undefined;

    const resolvedBookingPath = bookingPagePath || window.location.pathname;
    const contextFields = () => ({
      ...getAttributionDataLayerFields(),
      booking_provider: 'calendly',
      service_type: serviceType,
      booking_page_path: resolvedBookingPath,
      ...(landingPageType ? { landing_page_type: landingPageType } : {}),
      ...(variantId ? { variant_id: variantId } : {}),
    });

    const redirectAfterTracking = () => {
      if (!redirectOnBooked || disposed) return;
      if (window.location.pathname === redirectTo) return;
      window.location.assign(redirectTo);
    };

    const handleMessage = (messageEvent: MessageEvent) => {
      if (messageEvent.origin !== CALENDLY_ORIGIN) return;

      const data = messageEvent.data as CalendlyMessage;
      if (!data || typeof data !== 'object' || typeof data.event !== 'string') return;
      if (!data.event.startsWith('calendly.')) return;

      window.dataLayer = window.dataLayer || [];

      if (data.event === 'calendly.event_type_viewed') {
        window.dataLayer.push({
          event: 'calendly_event_type_viewed',
          ...contextFields(),
        });
        return;
      }

      if (data.event === 'calendly.date_and_time_selected') {
        window.dataLayer.push({
          event: 'calendly_date_and_time_selected',
          ...contextFields(),
        });
        return;
      }

      if (data.event !== 'calendly.event_scheduled') return;

      const eventUri = data.payload?.event?.uri;
      const inviteeUri = data.payload?.invitee?.uri;
      const dedupeIdentity = eventUri || inviteeUri || 'fallback';
      const dedupeKey = `kesher_booking_confirmed:${dedupeIdentity}`;

      if (safeSessionGet(dedupeKey) === 'true') return;
      safeSessionSet(dedupeKey, 'true');

      const bookingEvent: Record<string, unknown> = {
        event: 'booking_confirmed',
        ...contextFields(),
        booking_id_present: Boolean(eventUri || inviteeUri),
      };

      if (typeof value === 'number') {
        bookingEvent.value = value;
        bookingEvent.currency = currency;
      }

      window.dataLayer.push(bookingEvent);

      const attribution = getStoredAttribution();
      void sendBrowserBookingConfirmation({
        calendly_event_uri: eventUri,
        calendly_invitee_uri: inviteeUri,
        service_type: serviceType,
        booking_page_path: resolvedBookingPath,
        landing_page_type: landingPageType,
        variant_id: variantId || attribution.variant_id,
        entry_page_path: attribution.entry_page_path,
        utm_source: attribution.utm_source,
        utm_medium: attribution.utm_medium,
        utm_campaign: attribution.utm_campaign,
        utm_term: attribution.utm_term,
        utm_content: attribution.utm_content,
        google_click_id_present: attribution.google_click_id_present === true,
        observed_at: new Date().toISOString(),
      });

      if (redirectOnBooked) {
        let redirected = false;
        const redirectOnce = () => {
          if (redirected) return;
          redirected = true;
          redirectAfterTracking();
        };

        window.dataLayer.push({
          event: 'booking_redirect',
          ...contextFields(),
          eventCallback: redirectOnce,
          eventTimeout: 2000,
        });

        redirectTimer = window.setTimeout(redirectOnce, 2200);
      }
    };

    window.addEventListener('message', handleMessage);

    const initialize = async () => {
      try {
        await loadCalendlyScript();
        if (disposed) return;

        const activeEmbed = document.querySelector<HTMLElement>(
          `[${AUTO_RESIZE_ACTIVE_ATTRIBUTE}="true"]`,
        );
        if (activeEmbed && activeEmbed !== container) {
          throw new Error('Only one auto-resizing Calendly embed is allowed per page.');
        }

        const calendly = (window as WindowWithCalendly).Calendly;
        if (!calendly) throw new Error('Calendly API is unavailable.');

        container.setAttribute(AUTO_RESIZE_ACTIVE_ATTRIBUTE, 'true');
        container.replaceChildren();
        calendly.initInlineWidget({
          url: SITE_CONFIG.links.calendly,
          parentElement: container,
          resize: true,
          utm: getCalendlyUtm(),
        });
      } catch {
        if (!disposed) setLoadFailed(true);
      }
    };

    void initialize();

    return () => {
      disposed = true;
      window.removeEventListener('message', handleMessage);
      if (redirectTimer) window.clearTimeout(redirectTimer);
      container.removeAttribute(AUTO_RESIZE_ACTIVE_ATTRIBUTE);
    };
  }, [
    bookingPagePath,
    currency,
    landingPageType,
    redirectOnBooked,
    redirectTo,
    serviceType,
    value,
    variantId,
  ]);

  return (
    <div className={`${styles.embedShell} ${className || ''}`.trim()}>
      <div
        ref={containerRef}
        className={styles.embedContainer}
        aria-label={ariaLabel}
      />
      {loadFailed && (
        <p className={styles.status} role="status">
          לוח הזמנים לא נטען.{' '}
          <a href={SITE_CONFIG.links.calendly} target="_blank" rel="noopener noreferrer">
            פתחו את Calendly בחלון חדש
          </a>
        </p>
      )}
    </div>
  );
};

export default CalendlyBookingEmbed;
