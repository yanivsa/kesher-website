import { getAttributionDataLayerFields, getStoredAttribution } from './attribution';

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
    __kesherMeasurementMode?: 'gtm' | 'ga4' | 'disabled';
  }
}

type AnalyticsParams = Record<string, unknown>;

const BOOKING_START_KEY = 'kesher_booking_started_v1';
const CONVERSION_EVENTS = new Set([
  'phone_click',
  'whatsapp_click',
  'booking_start',
  'booking_complete',
  'generate_lead',
  'lead_submit',
]);
const recentEvents = new Map<string, number>();

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
    // Analytics must never block the user journey.
  }
};

const safeSessionRemove = (key: string) => {
  try {
    window.sessionStorage.removeItem(key);
  } catch {
    // Analytics must never block the user journey.
  }
};

const inferServiceType = (pathname: string): string | undefined => {
  if (pathname === '/couples-counseling-ashdod') return 'couples_counseling';
  const serviceMatch = pathname.match(/^\/services\/([^/]+)/);
  if (serviceMatch?.[1]) return serviceMatch[1].replace(/-/g, '_');
  if (pathname === '/appointment') return 'general_consultation';
  return undefined;
};

export const pushAnalyticsEvent = (eventName: string, params: AnalyticsParams = {}) => {
  if (typeof window === 'undefined') return;

  const attribution = getStoredAttribution();
  const serviceType = typeof params.service_type === 'string'
    ? params.service_type
    : inferServiceType(window.location.pathname);
  const payload: AnalyticsParams = {
    event: eventName,
    page_location: window.location.href,
    page_path: window.location.pathname,
    landing_page: attribution.entry_page_path || window.location.pathname,
    ...getAttributionDataLayerFields(),
    ...(serviceType ? { service_type: serviceType, service: serviceType } : {}),
    ...params,
  };

  const dedupeKey = CONVERSION_EVENTS.has(eventName)
    ? `${eventName}|${window.location.pathname}`
    : `${eventName}|${window.location.pathname}|${String(params.cta_location || '')}`;
  const now = Date.now();
  const previous = recentEvents.get(dedupeKey) || 0;
  if (now - previous < 750) return;
  recentEvents.set(dedupeKey, now);

  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push(payload);

  // When production is configured with a direct G-* measurement ID rather than
  // GTM, send custom events through gtag as well. In GTM mode, dataLayer is the
  // single source to avoid duplicate events.
  if (window.__kesherMeasurementMode === 'ga4' && typeof window.gtag === 'function') {
    const { event: _event, ...gaParams } = payload;
    window.gtag('event', eventName, gaParams);
  }
};

export const trackBookingStart = (params: AnalyticsParams = {}) => {
  if (typeof window === 'undefined') return;
  if (safeSessionGet(BOOKING_START_KEY) === 'true') return;
  safeSessionSet(BOOKING_START_KEY, 'true');
  pushAnalyticsEvent('booking_start', params);
};

export const resetBookingStart = () => {
  if (typeof window === 'undefined') return;
  safeSessionRemove(BOOKING_START_KEY);
};
