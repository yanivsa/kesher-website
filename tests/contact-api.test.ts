import { afterEach, describe, expect, it, vi } from 'vitest';
import { handleContactRequest } from '../functions/api/contact';

const validPayload = {
  kind: 'contact',
  name: 'Test User',
  email: 'test@example.com',
  phone: '050-1234567',
  service: 'couples',
  message: 'Test message',
  company: '',
  startedAt: Date.now() - 5_000,
};

const request = (body: unknown, method = 'POST') =>
  new Request('https://kesher.saharoni.com/api/contact', {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: method === 'POST' ? JSON.stringify(body) : undefined,
  });

afterEach(() => vi.unstubAllGlobals());

describe('contact API', () => {
  it('rejects unsupported methods', async () => {
    const response = await handleContactRequest(request({}, 'GET'));
    expect(response.status).toBe(405);
  });

  it('rejects invalid contact details before calling the provider', async () => {
    const provider = vi.fn();
    vi.stubGlobal('fetch', provider);
    const response = await handleContactRequest(request({ ...validPayload, email: 'bad' }));
    expect(response.status).toBe(400);
    expect(provider).not.toHaveBeenCalled();
  });

  it('rejects null and other non-object JSON bodies instead of throwing', async () => {
    const provider = vi.fn();
    vi.stubGlobal('fetch', provider);

    for (const body of [null, [], 'invalid']) {
      const response = await handleContactRequest(request(body));
      expect(response.status).toBe(400);
    }
    expect(provider).not.toHaveBeenCalled();
  });

  it('rejects oversized bodies even without a content-length header', async () => {
    const oversized = new Request('https://kesher.saharoni.com/api/contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'x'.repeat(21_000) }),
    });
    const response = await handleContactRequest(oversized);
    expect(response.status).toBe(413);
  });

  it('accepts honeypot spam without forwarding personal data', async () => {
    const provider = vi.fn();
    vi.stubGlobal('fetch', provider);
    const response = await handleContactRequest(request({ ...validPayload, company: 'spam' }));
    expect(response.status).toBe(200);
    expect(provider).not.toHaveBeenCalled();
  });

  it('forwards valid contact requests to the provider', async () => {
    const provider = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', provider);
    const response = await handleContactRequest(request(validPayload));
    expect(response.status).toBe(200);
    expect(provider).toHaveBeenCalledOnce();
  });

  it('returns a controlled error when the message provider is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));
    const response = await handleContactRequest(request(validPayload));
    expect(response.status).toBe(502);
    expect(await response.json()).toMatchObject({ success: false });
  });

  it('returns a controlled error when Turnstile is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));
    const response = await handleContactRequest(
      request({ ...validPayload, turnstileToken: 'token' }),
      { TURNSTILE_SECRET_KEY: 'secret' },
    );
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ success: false });
  });

  it('returns a real download URL for lead magnet requests', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 200 })));
    const response = await handleContactRequest(request({
      kind: 'lead_magnet',
      email: 'test@example.com',
      startedAt: Date.now() - 5_000,
    }));
    expect(await response.json()).toMatchObject({
      success: true,
      downloadUrl: '/guides/5-sentences-stop-an-argument.html',
    });
  });
});
