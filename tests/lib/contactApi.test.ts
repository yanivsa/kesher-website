import { afterEach, describe, expect, it, vi } from 'vitest';
import { submitContact, type ContactRequest } from '../../src/lib/contactApi';

const validRequest: ContactRequest = {
  kind: 'contact',
  name: 'Test User',
  email: 'test@example.com',
  phone: '050-1234567',
  startedAt: Date.now() - 5000,
};

describe('submitContact API wrapper', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('successfully submits a contact request', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, message: 'Success' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await submitContact(validRequest);

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith('/api/contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(validRequest),
    });
    expect(result).toEqual({ success: true, message: 'Success' });
  });

  it('successfully returns a downloadUrl for lead magnet requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, message: 'Success', downloadUrl: '/guide.pdf' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const result = await submitContact({ ...validRequest, kind: 'lead_magnet' });

    expect(result).toEqual({ success: true, message: 'Success', downloadUrl: '/guide.pdf' });
  });

  it('throws an error if response.ok is false', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ success: false, message: 'Internal Server Error' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(submitContact(validRequest)).rejects.toThrow('Internal Server Error');
  });

  it('throws an error if response.ok is true but success is false', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: false, message: 'Validation Failed' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(submitContact(validRequest)).rejects.toThrow('Validation Failed');
  });

  it('throws a default error message if result.message is missing', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ success: false }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(submitContact(validRequest)).rejects.toThrow('Request failed');
  });
});
