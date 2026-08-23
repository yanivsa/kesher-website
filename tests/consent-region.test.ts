import { describe, expect, it } from 'vitest';
import { requiresConsentForCountry } from '../functions/api/consent-region';

describe('regional consent policy', () => {
  it('does not require the blocking consent prompt for Israel', () => {
    expect(requiresConsentForCountry('IL')).toBe(false);
  });

  it('keeps the consent prompt for visitors outside Israel', () => {
    expect(requiresConsentForCountry('DE')).toBe(true);
    expect(requiresConsentForCountry('GB')).toBe(true);
    expect(requiresConsentForCountry('CH')).toBe(true);
    expect(requiresConsentForCountry('US')).toBe(true);
    expect(requiresConsentForCountry('CA')).toBe(true);
    expect(requiresConsentForCountry('AU')).toBe(true);
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
