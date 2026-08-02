import { useEffect, useRef } from 'react';

declare global {
  interface Window {
    dataLayer: Array<Record<string, unknown>>;
  }
}

export const useLandingPageAnalytics = (variantId: string = 'A') => {
  const scroll50Tracked = useRef(false);
  const scroll90Tracked = useRef(false);

  useEffect(() => {
    // 1. Capture UTM and click parameters in sessionStorage
    try {
      const searchParams = new URLSearchParams(window.location.search);
      const utmKeys = [
        'gclid',
        'gbraid',
        'wbraid',
        'utm_source',
        'utm_medium',
        'utm_campaign',
        'utm_term',
        'utm_content',
      ];
      utmKeys.forEach((key) => {
        const val = searchParams.get(key);
        if (val) {
          sessionStorage.setItem(`kesher_${key}`, val);
        }
      });
    } catch {
      // Ignore storage errors if private browsing restricts sessionStorage
    }

    // 2. Push landing_page_view event
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'landing_page_view',
      landing_page_path: '/couples-counseling-ashdod',
      landing_page_type: 'ashdod',
      service_type: 'couples_counseling',
      variant_id: variantId,
    });

    // 3. Calendly postMessage listener
    const handleMessage = (e: MessageEvent) => {
      // Validate origin strictly — only exact Calendly origin or same-origin for E2E testing
      const ALLOWED_ORIGINS = new Set(['https://calendly.com']);
      const isCalendlyOrigin = ALLOWED_ORIGINS.has(e.origin) || e.origin === window.location.origin;
      if (!isCalendlyOrigin) {
        return;
      }

      const data = e.data;
      if (!data || typeof data !== 'object') {
        return;
      }

      const eventName = data.event;
      window.dataLayer = window.dataLayer || [];

      if (eventName === 'calendly.event_type_viewed') {
        window.dataLayer.push({
          event: 'calendly_event_type_viewed',
          booking_provider: 'calendly',
          service_type: 'couples_counseling',
          variant_id: variantId,
          landing_page_path: '/couples-counseling-ashdod',
        });
      } else if (eventName === 'calendly.date_and_time_selected') {
        window.dataLayer.push({
          event: 'calendly_date_and_time_selected',
          booking_provider: 'calendly',
          service_type: 'couples_counseling',
          variant_id: variantId,
          landing_page_path: '/couples-counseling-ashdod',
        });
      } else if (eventName === 'calendly.event_scheduled') {
        // Deduplication mechanism using sessionStorage & payload uri
        const eventUri = data.payload?.event?.uri || `fallback_${Date.now()}`;
        const dedupKey = `kesher_booked_${eventUri}`;

        let alreadyFired = false;
        try {
          alreadyFired = sessionStorage.getItem(dedupKey) === 'true';
        } catch {
          // fallback
        }

        if (!alreadyFired) {
          try {
            sessionStorage.setItem(dedupKey, 'true');
          } catch {
            // ignore
          }

          window.dataLayer.push({
            event: 'booking_confirmed',
            booking_provider: 'calendly',
            service_type: 'couples_counseling',
            landing_page_type: 'ashdod',
            variant_id: variantId,
            value: 500,
            currency: 'ILS',
          });

          // Redirect via dataLayer eventCallback to ensure GTM fires first
          window.dataLayer.push({
            event: 'booking_redirect',
            eventCallback: () => {
              window.location.href = '/thank-you-booked';
            },
            eventTimeout: 2000,
          });
        }
      }
    };

    window.addEventListener('message', handleMessage);

    // 4. Scroll tracking (50% and 90%)
    const handleScroll = () => {
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (docHeight <= 0) return;

      const scrollPercent = (window.scrollY / docHeight) * 100;

      window.dataLayer = window.dataLayer || [];

      if (scrollPercent >= 50 && !scroll50Tracked.current) {
        scroll50Tracked.current = true;
        window.dataLayer.push({
          event: 'scroll_50',
          variant_id: variantId,
          landing_page_path: '/couples-counseling-ashdod',
        });
      }

      if (scrollPercent >= 90 && !scroll90Tracked.current) {
        scroll90Tracked.current = true;
        window.dataLayer.push({
          event: 'scroll_90',
          variant_id: variantId,
          landing_page_path: '/couples-counseling-ashdod',
        });
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });

    return () => {
      window.removeEventListener('message', handleMessage);
      window.removeEventListener('scroll', handleScroll);
    };
  }, []);

  const trackCtaClick = (ctaName: string, ctaLocation: string) => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'primary_cta_click',
      cta_name: ctaName,
      cta_location: ctaLocation,
      variant_id: variantId,
      landing_page_path: '/couples-counseling-ashdod',
    });
  };

  const trackSecondaryCtaClick = (ctaName: string, ctaLocation: string) => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'secondary_cta_click',
      cta_name: ctaName,
      cta_location: ctaLocation,
      variant_id: variantId,
      landing_page_path: '/couples-counseling-ashdod',
    });
  };

  const trackPhoneClick = () => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'phone_click',
      variant_id: variantId,
      landing_page_path: '/couples-counseling-ashdod',
    });
  };

  const trackWhatsappClick = () => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'whatsapp_click',
      variant_id: variantId,
      landing_page_path: '/couples-counseling-ashdod',
    });
  };

  const trackCalendlyOpen = () => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'calendly_open',
      variant_id: variantId,
      landing_page_path: '/couples-counseling-ashdod',
    });
  };

  return {
    trackCtaClick,
    trackSecondaryCtaClick,
    trackPhoneClick,
    trackWhatsappClick,
    trackCalendlyOpen,
  };
};
