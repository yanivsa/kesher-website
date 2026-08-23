export const requiresConsentForCountry = (country?: string | null) => {
  const normalized = country?.trim().toUpperCase();

  // The site's paid-search campaign is Israeli. Suppress the blocking prompt
  // only for visitors Cloudflare identifies as being in Israel. Keep the
  // existing consent flow everywhere else rather than making legal assumptions
  // about other jurisdictions. Unknown geolocation therefore fails closed.
  return normalized !== 'IL';
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
