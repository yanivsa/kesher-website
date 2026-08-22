const CONSENT_REQUIRED_COUNTRIES = new Set([
  // European Economic Area (EU + Iceland, Liechtenstein and Norway)
  'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR',
  'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK',
  'SI', 'ES', 'SE', 'IS', 'LI', 'NO',
  // Google EU User Consent Policy also covers the UK and Switzerland.
  'GB', 'CH',
]);

export const requiresConsentForCountry = (country?: string | null) => {
  const normalized = country?.trim().toUpperCase();

  // Fail closed when Cloudflare cannot determine the visitor country.
  if (!normalized || normalized === 'XX' || normalized === 'T1') return true;

  return CONSENT_REQUIRED_COUNTRIES.has(normalized);
};

export const onRequest: PagesFunction = async (context) => {
  const country = context.request.cf?.country;
  const requiresConsent = requiresConsentForCountry(country);

  return new Response(JSON.stringify({ requiresConsent }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'private, no-store, max-age=0',
      'X-Content-Type-Options': 'nosniff',
    },
  });
};
