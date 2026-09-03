import { describe, expect, it } from 'vitest';
import { CONTACT_SERVICE_OPTIONS, resolveContactService } from '../src/lib/contactServices';

describe('contact service selection', () => {
  it('supports lecture and workshop inquiries as a first-class service', () => {
    expect(CONTACT_SERVICE_OPTIONS).toContainEqual({
      value: 'lectures',
      label: 'הזמנת הרצאה או סדנה',
    });
    expect(resolveContactService('lectures')).toBe('lectures');
  });

  it('falls back to couples counseling for unknown or missing service values', () => {
    expect(resolveContactService('unknown')).toBe('couples');
    expect(resolveContactService(null)).toBe('couples');
  });
});
