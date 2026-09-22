import { afterEach, describe, expect, it, vi } from 'vitest';
import { handleContactRequest } from '../functions/api/contact';

const validPayload = {
  kind: 'contact' as const,
  name: 'Test User',
  email: 'test@example.com',
  phone: '050-1234567',
  service: 'couples',
  message: 'Test message',
  company: '',
  startedAt: Date.now() - 5_000,
  turnstileToken: 'test-token',
};

const turnstileEnv = { TURNSTILE_SECRET_KEY: 'test-secret' };

const request = (body: unknown, method = 'POST') =>
  new Request('https://kesher.saharoni.com/api/contact', {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: method === 'POST' ? JSON.stringify(body) : undefined,
  });

const verifiedTurnstileResponse = (action: 'contact' | 'lead_magnet') =>
  new Response(JSON.stringify({
    success: true,
    hostname: 'kesher.saharoni.com',
    action,
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

const successfulFetch = (action: 'contact' | 'lead_magnet' = 'contact') =>
  vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('challenges.cloudflare.com/turnstile/v0/siteverify')) {
      return verifiedTurnstileResponse(action);
    }
    return new Response('{}', { status: 200 });
  });

afterEach(() => vi.unstubAllGlobals());

describe('contact API', () => {
  it('rejects unsupported methods', async () => {
    const response = await handleContactRequest(request({}, 'GET'));
    expect(response.status).toBe(405);
  });

  it('rejects invalid contact details before calling external services', async () => {
    const provider = vi.fn();
    vi.stubGlobal('fetch', provider);
    const response = await handleContactRequest(
      request({ ...validPayload, email: 'bad' }),
      turnstileEnv,
    );
    expect(response.status).toBe(400);
    expect(provider).not.toHaveBeenCalled();
  });

  it('rejects null and other non-object JSON bodies instead of throwing', async () => {
    const provider = vi.fn();
    vi.stubGlobal('fetch', provider);

    for (const body of [null, [], 'invalid']) {
      const response = await handleContactRequest(request(body), turnstileEnv);
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
    const response = await handleContactRequest(oversized, turnstileEnv);
    expect(response.status).toBe(413);
  });

  it('accepts honeypot spam without forwarding personal data', async () => {
    const provider = vi.fn();
    vi.stubGlobal('fetch', provider);
    const response = await handleContactRequest(
      request({ ...validPayload, company: 'spam' }),
      turnstileEnv,
    );
    expect(response.status).toBe(200);
    expect(provider).not.toHaveBeenCalled();
  });

  it('fails closed when the Turnstile secret is missing', async () => {
    const provider = vi.fn();
    vi.stubGlobal('fetch', provider);
    const response = await handleContactRequest(request(validPayload), {});
    expect(response.status).toBe(503);
    expect(provider).not.toHaveBeenCalled();
  });

  it('requires a Turnstile token when verification is configured', async () => {
    const provider = vi.fn();
    vi.stubGlobal('fetch', provider);
    const { turnstileToken: _token, ...withoutToken } = validPayload;
    const response = await handleContactRequest(request(withoutToken), turnstileEnv);
    expect(response.status).toBe(400);
    expect(provider).not.toHaveBeenCalled();
  });

  it('rejects Turnstile results for the wrong hostname or action', async () => {
    const wrongHost = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      success: true,
      hostname: 'attacker.example',
      action: 'contact',
    }), { status: 200 }));
    vi.stubGlobal('fetch', wrongHost);
    expect((await handleContactRequest(request(validPayload), turnstileEnv)).status).toBe(403);

    const wrongAction = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      success: true,
      hostname: 'kesher.saharoni.com',
      action: 'lead_magnet',
    }), { status: 200 }));
    vi.stubGlobal('fetch', wrongAction);
    expect((await handleContactRequest(request(validPayload), turnstileEnv)).status).toBe(403);
  });

  it('forwards a valid contact request only after successful Turnstile verification', async () => {
    const fetchMock = successfulFetch('contact');
    vi.stubGlobal('fetch', fetchMock);
    const response = await handleContactRequest(request(validPayload), turnstileEnv);
    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('returns a controlled error when the message provider is unavailable', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('challenges.cloudflare.com/turnstile/v0/siteverify')) {
        return verifiedTurnstileResponse('contact');
      }
      throw new Error('network down');
    });
    vi.stubGlobal('fetch', fetchMock);
    const response = await handleContactRequest(request(validPayload), turnstileEnv);
    expect(response.status).toBe(502);
    expect(await response.json()).toMatchObject({ success: false });
  });

  it('returns a controlled error when Turnstile is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));
    const response = await handleContactRequest(request(validPayload), turnstileEnv);
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({ success: false });
  });

  it('returns a real download URL for verified lead magnet requests', async () => {
    const fetchMock = successfulFetch('lead_magnet');
    vi.stubGlobal('fetch', fetchMock);
    const response = await handleContactRequest(request({
      kind: 'lead_magnet',
      email: 'test@example.com',
      startedAt: Date.now() - 5_000,
      turnstileToken: 'test-token',
    }), turnstileEnv);
    expect(await response.json()).toMatchObject({
      success: true,
      downloadUrl: '/guides/5-sentences-stop-an-argument.html',
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
