import { describe, expect, it } from 'vitest';
import { requiresConsentForCountry } from '../functions/api/consent-region';

describe('regional consent policy', () => {
  it('does not require the blocking consent prompt for Israel', () => {
    expect(requiresConsentForCountry('IL')).toBe(false);
  });

  it('requires consent for EEA, UK and Swiss visitors', () => {
    expect(requiresConsentForCountry('DE')).toBe(true);
    expect(requiresConsentForCountry('NO')).toBe(true);
    expect(requiresConsentForCountry('GB')).toBe(true);
    expect(requiresConsentForCountry('CH')).toBe(true);
  });

  it('allows other known non-regulated countries without the blocking prompt', () => {
    expect(requiresConsentForCountry('US')).toBe(false);
    expect(requiresConsentForCountry('CA')).toBe(false);
    expect(requiresConsentForCountry('AU')).toBe(false);
  });

  it('fails closed when the visitor country is unavailable or unknown', () => {
    expect(requiresConsentForCountry()).toBe(true);
    expect(requiresConsentForCountry('XX')).toBe(true);
    expect(requiresConsentForCountry('T1')).toBe(true);
  });

  it('normalizes the Cloudflare country code', () => {
    expect(requiresConsentForCountry(' il ')).toBe(false);
    expect(requiresConsentForCountry(' de ')).toBe(true);
  });
});
