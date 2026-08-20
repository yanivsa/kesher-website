import { useEffect, useRef } from 'react';

export const useLandingPageAnalytics = (variantId: string = 'A') => {
  const scroll50Tracked = useRef(false);
  const scroll90Tracked = useRef(false);

  useEffect(() => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'landing_page_view',
      landing_page_path: '/couples-counseling-ashdod',
      landing_page_type: 'ashdod',
      service_type: 'couples_counseling',
      variant_id: variantId,
    });

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
      window.removeEventListener('scroll', handleScroll);
    };
  }, [variantId]);

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
