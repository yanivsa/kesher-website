export const ATTRIBUTION_STORAGE_PREFIX = 'kesher_attr_';

export const UTM_KEYS = [
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_term',
  'utm_content',
] as const;

type UtmKey = (typeof UTM_KEYS)[number];

type AttributionRecord = Partial<Record<UtmKey, string>> & {
  entry_page_path?: string;
  variant_id?: string;
  google_click_id_present?: boolean;
};

export type CalendlyUtm = {
  utmSource?: string;
  utmMedium?: string;
  utmCampaign?: string;
  utmTerm?: string;
  utmContent?: string;
};

declare global {
  interface Window {
    dataLayer: Array<Record<string, unknown>>;
  }
}

const MAX_UTM_LENGTH = 254;
const GOOGLE_CLICK_KEYS = ['gclid', 'gbraid', 'wbraid'] as const;

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
    // Storage can be unavailable in hardened/private browsing modes.
  }
};

const sanitizeAttributionValue = (value: string | null): string | undefined => {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  return trimmed.slice(0, MAX_UTM_LENGTH);
};

export const captureSiteAttribution = (pathname: string, search: string) => {
  if (typeof window === 'undefined') return;

  const params = new URLSearchParams(search);

  if (!safeSessionGet(`${ATTRIBUTION_STORAGE_PREFIX}entry_page_path`)) {
    safeSessionSet(`${ATTRIBUTION_STORAGE_PREFIX}entry_page_path`, pathname || '/');
  }

  UTM_KEYS.forEach((key) => {
    const value = sanitizeAttributionValue(params.get(key));
    if (value) {
      safeSessionSet(`${ATTRIBUTION_STORAGE_PREFIX}${key}`, value);
    }
  });

  const variant = sanitizeAttributionValue(params.get('variant'));
  if (variant) {
    safeSessionSet(`${ATTRIBUTION_STORAGE_PREFIX}variant_id`, variant.toUpperCase());
  }

  // Do not persist Google click identifiers ourselves. Google Tag / Conversion
  // Linker owns click-id storage and applies Consent Mode to that storage.
  if (GOOGLE_CLICK_KEYS.some((key) => Boolean(params.get(key)))) {
    safeSessionSet(`${ATTRIBUTION_STORAGE_PREFIX}google_click_id_present`, 'true');
  }
};

export const getStoredAttribution = (): AttributionRecord => {
  if (typeof window === 'undefined') return {};

  const result: AttributionRecord = {};
  UTM_KEYS.forEach((key) => {
    const value = safeSessionGet(`${ATTRIBUTION_STORAGE_PREFIX}${key}`);
    if (value) result[key] = value;
  });

  const entryPage = safeSessionGet(`${ATTRIBUTION_STORAGE_PREFIX}entry_page_path`);
  const variant = safeSessionGet(`${ATTRIBUTION_STORAGE_PREFIX}variant_id`);
  const googleClickIdPresent = safeSessionGet(
    `${ATTRIBUTION_STORAGE_PREFIX}google_click_id_present`,
  );

  if (entryPage) result.entry_page_path = entryPage;
  if (variant) result.variant_id = variant;
  if (googleClickIdPresent === 'true') result.google_click_id_present = true;

  return result;
};

export const getCalendlyUtm = (): CalendlyUtm => {
  const attribution = getStoredAttribution();
  return {
    utmSource: attribution.utm_source,
    utmMedium: attribution.utm_medium,
    utmCampaign: attribution.utm_campaign,
    utmTerm: attribution.utm_term,
    utmContent: attribution.utm_content,
  };
};

export const getAttributionDataLayerFields = (): Record<string, unknown> => {
  const attribution = getStoredAttribution();
  return {
    entry_page_path: attribution.entry_page_path,
    variant_id: attribution.variant_id,
    utm_source: attribution.utm_source,
    utm_medium: attribution.utm_medium,
    utm_campaign: attribution.utm_campaign,
    utm_term: attribution.utm_term,
    utm_content: attribution.utm_content,
    google_click_id_present: attribution.google_click_id_present === true,
  };
};
