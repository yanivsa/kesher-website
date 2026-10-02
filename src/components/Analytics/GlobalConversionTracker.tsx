import React, { useEffect } from 'react';
import { pushAnalyticsEvent, trackBookingStart } from '../../lib/analytics';

const getCtaLocation = (link: HTMLAnchorElement): string => {
  const explicit = link.closest<HTMLElement>('[data-analytics-location]')?.dataset.analyticsLocation;
  if (explicit) return explicit;
  if (link.closest('header')) return 'header';
  if (link.closest('footer')) return 'footer';
  if (link.closest('#contact')) return 'contact';
  return 'page';
};

const getCtaName = (link: HTMLAnchorElement): string | undefined => {
  const label = link.getAttribute('aria-label') || link.textContent || '';
  const clean = label.replace(/\s+/g, ' ').trim();
  return clean ? clean.slice(0, 120) : undefined;
};

const getLandingContext = (link: HTMLAnchorElement): Record<string, string> => {
  const owner = link.closest<HTMLElement>(
    '[data-analytics-service-type], [data-analytics-landing-page-type], [data-analytics-variant-id]',
  );
  if (!owner) return {};

  return {
    ...(owner.dataset.analyticsServiceType
      ? { service_type: owner.dataset.analyticsServiceType }
      : {}),
    ...(owner.dataset.analyticsLandingPageType
      ? { landing_page_type: owner.dataset.analyticsLandingPageType }
      : {}),
    ...(owner.dataset.analyticsVariantId
      ? { variant_id: owner.dataset.analyticsVariantId }
      : {}),
  };
};

const GlobalConversionTracker: React.FC = () => {
  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const link = target.closest<HTMLAnchorElement>('a[href]');
      if (!link) return;

      const rawHref = link.getAttribute('href') || '';
      const href = rawHref.toLowerCase();
      const context = {
        ...getLandingContext(link),
        cta_location: getCtaLocation(link),
        ...(getCtaName(link) ? { cta_name: getCtaName(link) } : {}),
      };

      if (href.startsWith('tel:')) {
        pushAnalyticsEvent('phone_click', context);
        return;
      }

      if (href.includes('wa.me/') || href.includes('whatsapp.com/') || href.includes('api.whatsapp.com/')) {
        pushAnalyticsEvent('whatsapp_click', context);
        return;
      }

      if (href.includes('/appointment') || href.includes('calendly.com/')) {
        trackBookingStart(context);
      }
    };

    // Capture phase records the actual clicked CTA before route navigation and
    // lets legacy component handlers be safely deduplicated by analytics.ts.
    document.addEventListener('click', handleClick, true);
    return () => document.removeEventListener('click', handleClick, true);
  }, []);

  return null;
};

export default GlobalConversionTracker;
