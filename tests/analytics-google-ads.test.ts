import { beforeEach, describe, expect, it, vi } from 'vitest';
import { pushAnalyticsEvent } from '../src/lib/analytics';

const ADS_DESTINATIONS = {
  lead_submit: 'AW-985068949/V3vgCPCR_-scEJXr29UD',
  booking_complete: 'AW-985068949/CAZLCPOR_-scEJXr29UD',
  phone_click: 'AW-985068949/GZrxCPaR_-scEJXr29UD',
  whatsapp_click: 'AW-985068949/k2mNCPmR_-scEJXr29UD',
} as const;

let pathCounter = 0;

describe('Google Ads conversion forwarding', () => {
  beforeEach(() => {
    pathCounter += 1;
    window.history.replaceState({}, '', `/analytics-test-${pathCounter}`);
    window.sessionStorage.clear();
    window.dataLayer = [];
    window.__kesherMeasurementMode = 'ga4';
    window.gtag = vi.fn();
  });

  for (const [eventName, destination] of Object.entries(ADS_DESTINATIONS)) {
    it(`forwards ${eventName} to its Google Ads conversion action`, () => {
      pushAnalyticsEvent(eventName);

      expect(window.gtag).toHaveBeenCalledWith(
        'event',
        'conversion',
        expect.objectContaining({
          send_to: destination,
          value: 1,
          currency: 'ILS',
        }),
      );
    });
  }

  it.each(['booking_start', 'generate_lead'])('does not treat %s as a Google Ads conversion', (eventName) => {
    pushAnalyticsEvent(eventName);

    const conversionCalls = vi.mocked(window.gtag!).mock.calls.filter(
      ([command, name]) => command === 'event' && name === 'conversion',
    );
    expect(conversionCalls).toHaveLength(0);
  });

  it('leaves direct Google Ads conversion reporting to GTM in GTM mode', () => {
    window.__kesherMeasurementMode = 'gtm';

    pushAnalyticsEvent('lead_submit');

    const conversionCalls = vi.mocked(window.gtag!).mock.calls.filter(
      ([command, name]) => command === 'event' && name === 'conversion',
    );
    expect(conversionCalls).toHaveLength(0);
  });

  it('does not report the same conversion twice within the dedupe window', () => {
    pushAnalyticsEvent('phone_click');
    pushAnalyticsEvent('phone_click');

    const conversionCalls = vi.mocked(window.gtag!).mock.calls.filter(
      ([command, name]) => command === 'event' && name === 'conversion',
    );
    expect(conversionCalls).toHaveLength(1);
  });
});
