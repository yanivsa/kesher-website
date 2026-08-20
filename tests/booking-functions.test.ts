import { describe, expect, it } from 'vitest';
import { handleBrowserBookingConfirmation } from '../functions/api/booking/browser-confirmation';
import { handleCalendlyWebhook } from '../functions/api/calendly/webhook';

const eventUri = 'https://api.calendly.com/scheduled_events/event-123';
const inviteeUri = `${eventUri}/invitees/invitee-456`;

const makeSignature = async (rawBody: string, key: string, timestamp = Math.floor(Date.now() / 1000)) => {
  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(key),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const digest = await crypto.subtle.sign(
    'HMAC',
    cryptoKey,
    new TextEncoder().encode(`${timestamp}.${rawBody}`),
  );
  const hex = [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
  return `t=${timestamp},v1=${hex}`;
};

const createFakeDb = () => {
  const calls: unknown[][] = [];
  const db = {
    prepare: () => ({
      bind: (...values: unknown[]) => ({
        run: async () => {
          calls.push(values);
          return { success: true };
        },
      }),
    }),
  } as unknown as D1Database;
  return { db, calls };
};

const createFakeKv = () => {
  const values = new Map<string, string>();
  const puts: Array<{ key: string; value: string }> = [];
  const kv = {
    get: async (key: string, type?: string) => {
      const value = values.get(key);
      if (value === undefined) return null;
      return type === 'json' ? JSON.parse(value) : value;
    },
    put: async (key: string, value: string) => {
      values.set(key, value);
      puts.push({ key, value });
    },
  } as unknown as KVNamespace;
  return { kv, puts, values };
};

describe('browser booking confirmation endpoint', () => {
  it('accepts an official Calendly event URI without requiring storage', async () => {
    const request = new Request('https://kesher.saharoni.com/api/booking/browser-confirmation', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Origin: 'https://kesher.saharoni.com',
      },
      body: JSON.stringify({
        calendly_event_uri: eventUri,
        calendly_invitee_uri: inviteeUri,
        utm_source: 'google',
        utm_medium: 'cpc',
      }),
    });

    const response = await handleBrowserBookingConfirmation(request, {});
    expect(response.status).toBe(202);
    expect(await response.json()).toMatchObject({ success: true, stored: false });
  });

  it('rejects cross-origin writes and non-Calendly identifiers', async () => {
    const crossOrigin = new Request('https://kesher.saharoni.com/api/booking/browser-confirmation', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Origin: 'https://attacker.example',
      },
      body: JSON.stringify({ calendly_event_uri: eventUri }),
    });
    expect((await handleBrowserBookingConfirmation(crossOrigin, {})).status).toBe(403);

    const invalidUri = new Request('https://kesher.saharoni.com/api/booking/browser-confirmation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ calendly_event_uri: 'not-calendly' }),
    });
    expect((await handleBrowserBookingConfirmation(invalidUri, {})).status).toBe(400);
  });

  it('stores browser attribution in KV without requiring D1', async () => {
    const { kv, puts } = createFakeKv();
    const request = new Request('https://kesher.saharoni.com/api/booking/browser-confirmation', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Origin: 'https://kesher.saharoni.com',
      },
      body: JSON.stringify({
        calendly_event_uri: eventUri,
        calendly_invitee_uri: inviteeUri,
        service_type: 'couples_counseling',
        utm_source: 'google',
        utm_campaign: 'ashdod_search',
        google_click_id_present: true,
      }),
    });

    const response = await handleBrowserBookingConfirmation(request, { BOOKING_KV: kv });
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ success: true, stored: true, storage: 'kv' });
    expect(puts).toHaveLength(1);
    expect(puts[0].key).toBe('booking:browser:event-123');
    expect(JSON.parse(puts[0].value)).toMatchObject({
      channel: 'browser',
      calendly_event_uri: eventUri,
      utm_source: 'google',
      utm_campaign: 'ashdod_search',
      google_click_id_present: true,
    });
  });
});

describe('Calendly webhook endpoint', () => {
  it('fails closed when webhook verification or booking storage is not configured', async () => {
    const request = new Request('https://kesher.saharoni.com/api/calendly/webhook', {
      method: 'POST',
      body: '{}',
    });
    expect((await handleCalendlyWebhook(request, {})).status).toBe(503);
  });

  it('rejects an invalid webhook signature', async () => {
    const { db } = createFakeDb();
    const request = new Request('https://kesher.saharoni.com/api/calendly/webhook', {
      method: 'POST',
      headers: { 'Calendly-Webhook-Signature': 't=1,v1=bad' },
      body: '{}',
    });
    const response = await handleCalendlyWebhook(request, {
      BOOKING_DB: db,
      CALENDLY_WEBHOOK_SIGNING_KEY: 'test-signing-key',
    });
    expect(response.status).toBe(401);
  });

  it('verifies a signed invitee.created event and reconciles UTM data in D1', async () => {
    const { db, calls } = createFakeDb();
    const signingKey = 'test-signing-key';
    const rawBody = JSON.stringify({
      event: 'invitee.created',
      created_at: '2026-08-20T04:00:00.000000Z',
      payload: {
        uri: inviteeUri,
        event: eventUri,
        rescheduled: false,
        tracking: {
          utm_source: 'google',
          utm_medium: 'cpc',
          utm_campaign: 'ashdod_search',
          utm_term: 'ייעוץ זוגי אשדוד',
          utm_content: 'ad_a',
        },
      },
    });
    const signature = await makeSignature(rawBody, signingKey);
    const request = new Request('https://kesher.saharoni.com/api/calendly/webhook', {
      method: 'POST',
      headers: { 'Calendly-Webhook-Signature': signature },
      body: rawBody,
    });

    const response = await handleCalendlyWebhook(request, {
      BOOKING_DB: db,
      CALENDLY_WEBHOOK_SIGNING_KEY: signingKey,
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ success: true, reconciled: true, storage: 'd1' });
    expect(calls).toHaveLength(1);
    expect(calls[0][0]).toBe(eventUri);
    expect(calls[0][1]).toBe(inviteeUri);
    expect(calls[0][3]).toBe('invitee.created');
    expect(calls[0][4]).toBe('webhook_verified');
    expect(calls[0][8]).toBe('google');
    expect(calls[0][10]).toBe('ashdod_search');
  });

  it('stores a signed webhook in KV and preserves the newest lifecycle event', async () => {
    const { kv, puts, values } = createFakeKv();
    const signingKey = 'test-signing-key';

    const createdBody = JSON.stringify({
      event: 'invitee.created',
      created_at: '2026-08-20T04:00:00.000000Z',
      payload: {
        uri: inviteeUri,
        event: eventUri,
        rescheduled: false,
        tracking: { utm_source: 'google', utm_campaign: 'ashdod_search' },
      },
    });
    const createdRequest = new Request('https://kesher.saharoni.com/api/calendly/webhook', {
      method: 'POST',
      headers: { 'Calendly-Webhook-Signature': await makeSignature(createdBody, signingKey) },
      body: createdBody,
    });
    const createdResponse = await handleCalendlyWebhook(createdRequest, {
      BOOKING_KV: kv,
      CALENDLY_WEBHOOK_SIGNING_KEY: signingKey,
    });
    expect(createdResponse.status).toBe(200);
    expect(await createdResponse.json()).toMatchObject({ storage: 'kv' });

    const canceledBody = JSON.stringify({
      event: 'invitee.canceled',
      created_at: '2026-08-20T05:00:00.000000Z',
      payload: {
        uri: inviteeUri,
        event: eventUri,
        rescheduled: true,
        new_invitee: `${eventUri}/invitees/new-invitee`,
      },
    });
    const canceledRequest = new Request('https://kesher.saharoni.com/api/calendly/webhook', {
      method: 'POST',
      headers: { 'Calendly-Webhook-Signature': await makeSignature(canceledBody, signingKey) },
      body: canceledBody,
    });
    const canceledResponse = await handleCalendlyWebhook(canceledRequest, {
      BOOKING_KV: kv,
      CALENDLY_WEBHOOK_SIGNING_KEY: signingKey,
    });
    expect(canceledResponse.status).toBe(200);

    expect(puts).toHaveLength(2);
    expect(puts[0].key).toBe('booking:webhook:event-123');
    const latest = JSON.parse(values.get('booking:webhook:event-123') || '{}');
    expect(latest).toMatchObject({ status: 'rescheduled', rescheduled: true });
  });

  it('marks a signed reschedule cancellation in D1 without creating a second conversion path', async () => {
    const { db, calls } = createFakeDb();
    const signingKey = 'test-signing-key';
    const rawBody = JSON.stringify({
      event: 'invitee.canceled',
      payload: {
        uri: inviteeUri,
        event: eventUri,
        rescheduled: true,
        new_invitee: `${eventUri}/invitees/new-invitee`,
      },
    });
    const signature = await makeSignature(rawBody, signingKey);
    const request = new Request('https://kesher.saharoni.com/api/calendly/webhook', {
      method: 'POST',
      headers: { 'Calendly-Webhook-Signature': signature },
      body: rawBody,
    });

    const response = await handleCalendlyWebhook(request, {
      BOOKING_DB: db,
      CALENDLY_WEBHOOK_SIGNING_KEY: signingKey,
    });

    expect(response.status).toBe(200);
    expect(calls[0][4]).toBe('rescheduled');
    expect(calls[0][5]).toBe(1);
  });
});
