import { useEffect, useRef } from 'react';
import { pushAnalyticsEvent, trackBookingStart } from '../lib/analytics';

export interface LandingPageAnalyticsOptions {
  variantId?: string;
  landingPagePath?: string;
  landingPageType?: string;
  serviceType?: string;
}

export function useLandingPageAnalytics(variantId?: string): {
  trackCtaClick: (ctaName: string, ctaLocation: string) => void;
  trackSecondaryCtaClick: (ctaName: string, ctaLocation: string) => void;
  trackPhoneClick: () => void;
  trackWhatsappClick: () => void;
  trackCalendlyOpen: () => void;
  trackFaqInteraction: (faqIndex?: number) => void;
};
export function useLandingPageAnalytics(options: LandingPageAnalyticsOptions): {
  trackCtaClick: (ctaName: string, ctaLocation: string) => void;
  trackSecondaryCtaClick: (ctaName: string, ctaLocation: string) => void;
  trackPhoneClick: () => void;
  trackWhatsappClick: () => void;
  trackCalendlyOpen: () => void;
  trackFaqInteraction: (faqIndex?: number) => void;
};
export function useLandingPageAnalytics(
  optionsOrVariantId: string | LandingPageAnalyticsOptions = 'A',
) {
  const scroll50Tracked = useRef(false);
  const scroll90Tracked = useRef(false);

  const options: LandingPageAnalyticsOptions =
    typeof optionsOrVariantId === 'string'
      ? { variantId: optionsOrVariantId }
      : optionsOrVariantId || {};

  const variantId = options.variantId || 'A';
  const landingPagePath = options.landingPagePath || '/couples-counseling-ashdod';
  const landingPageType = options.landingPageType || 'ashdod';
  const serviceType = options.serviceType || 'couples_counseling';

  useEffect(() => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'landing_page_view',
      landing_page_path: landingPagePath,
      landing_page_type: landingPageType,
      service_type: serviceType,
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
          landing_page_path: landingPagePath,
          landing_page_type: landingPageType,
          service_type: serviceType,
        });
      }

      if (scrollPercent >= 90 && !scroll90Tracked.current) {
        scroll90Tracked.current = true;
        window.dataLayer.push({
          event: 'scroll_90',
          variant_id: variantId,
          landing_page_path: landingPagePath,
          landing_page_type: landingPageType,
          service_type: serviceType,
        });
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });

    return () => {
      window.removeEventListener('scroll', handleScroll);
    };
  }, [variantId, landingPagePath, landingPageType, serviceType]);

  const trackCtaClick = (ctaName: string, ctaLocation: string) => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'primary_cta_click',
      cta_name: ctaName,
      cta_location: ctaLocation,
      variant_id: variantId,
      landing_page_path: landingPagePath,
      landing_page_type: landingPageType,
      service_type: serviceType,
    });
  };

  const trackSecondaryCtaClick = (ctaName: string, ctaLocation: string) => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'secondary_cta_click',
      cta_name: ctaName,
      cta_location: ctaLocation,
      variant_id: variantId,
      landing_page_path: landingPagePath,
      landing_page_type: landingPageType,
      service_type: serviceType,
    });
  };

  const conversionContext = {
    variant_id: variantId,
    landing_page_path: landingPagePath,
    landing_page_type: landingPageType,
    service_type: serviceType,
  };

  const trackPhoneClick = () => {
    pushAnalyticsEvent('phone_click', { ...conversionContext, cta_location: 'landing_page' });
  };

  const trackWhatsappClick = () => {
    pushAnalyticsEvent('whatsapp_click', { ...conversionContext, cta_location: 'landing_page' });
  };

  const trackCalendlyOpen = () => {
    pushAnalyticsEvent('calendly_open', conversionContext);
    trackBookingStart({ ...conversionContext, cta_location: 'landing_page' });
  };

  const trackFaqInteraction = (faqIndex?: number) => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'faq_interaction',
      ...(typeof faqIndex === 'number' ? { faq_index: faqIndex } : {}),
      variant_id: variantId,
      landing_page_path: landingPagePath,
      landing_page_type: landingPageType,
      service_type: serviceType,
    });
  };

  return {
    trackCtaClick,
    trackSecondaryCtaClick,
    trackPhoneClick,
    trackWhatsappClick,
    trackCalendlyOpen,
    trackFaqInteraction,
  };
}
