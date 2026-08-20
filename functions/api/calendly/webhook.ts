interface CalendlyWebhookEnv {
  BOOKING_DB?: D1Database;
  CALENDLY_WEBHOOK_SIGNING_KEY?: string;
}

type CalendlyTracking = {
  utm_source?: unknown;
  utm_medium?: unknown;
  utm_campaign?: unknown;
  utm_term?: unknown;
  utm_content?: unknown;
};

type CalendlyWebhookPayload = {
  uri?: unknown;
  event?: unknown;
  scheduled_event?: { uri?: unknown };
  status?: unknown;
  rescheduled?: unknown;
  old_invitee?: unknown;
  new_invitee?: unknown;
  tracking?: CalendlyTracking;
};

type CalendlyWebhookBody = {
  event?: unknown;
  created_at?: unknown;
  payload?: CalendlyWebhookPayload;
};

const MAX_BODY_BYTES = 100_000;
const SIGNATURE_MAX_AGE_SECONDS = 5 * 60;
const CALENDLY_EVENT_PREFIX = "https://api.calendly.com/scheduled_events/";

const json = (body: object, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });

const clean = (value: unknown, maxLength: number) =>
  typeof value === "string" ? value.trim().slice(0, maxLength) : "";

const cleanNullable = (value: unknown, maxLength: number) => {
  const result = clean(value, maxLength);
  return result || null;
};

const parseSignatureHeader = (header: string) => {
  const parts = header.split(",").map((part) => part.trim());
  const timestamp = parts.find((part) => part.startsWith("t="))?.slice(2) || "";
  const signatures = parts
    .filter((part) => part.startsWith("v1="))
    .map((part) => part.slice(3))
    .filter(Boolean);
  return { timestamp, signatures };
};

const bytesToHex = (bytes: ArrayBuffer) =>
  [...new Uint8Array(bytes)].map((byte) => byte.toString(16).padStart(2, "0")).join("");

const timingSafeEqual = (left: string, right: string) => {
  if (left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
};

const verifySignature = async (rawBody: string, header: string, signingKey: string) => {
  const { timestamp, signatures } = parseSignatureHeader(header);
  if (!timestamp || signatures.length === 0) return false;

  const timestampSeconds = Number(timestamp);
  if (!Number.isFinite(timestampSeconds)) return false;
  const ageSeconds = Math.abs(Date.now() / 1000 - timestampSeconds);
  if (ageSeconds > SIGNATURE_MAX_AGE_SECONDS) return false;

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(signingKey),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const digest = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(`${timestamp}.${rawBody}`),
  );
  const expected = bytesToHex(digest);

  return signatures.some((signature) => timingSafeEqual(expected, signature));
};

const getEventUri = (payload: CalendlyWebhookPayload) => {
  const directEvent = clean(payload.event, 500);
  if (directEvent.startsWith(CALENDLY_EVENT_PREFIX)) return directEvent;
  const scheduledEvent = clean(payload.scheduled_event?.uri, 500);
  if (scheduledEvent.startsWith(CALENDLY_EVENT_PREFIX)) return scheduledEvent;
  return "";
};

export async function handleCalendlyWebhook(
  request: Request,
  env: CalendlyWebhookEnv = {},
) {
  if (request.method !== "POST") {
    return json({ success: false, message: "Method not allowed" }, 405);
  }

  if (!env.CALENDLY_WEBHOOK_SIGNING_KEY) {
    return json({ success: false, message: "Webhook verification is not configured" }, 503);
  }
  if (!env.BOOKING_DB) {
    return json({ success: false, message: "Booking reconciliation storage is not configured" }, 503);
  }

  const contentLength = Number(request.headers.get("content-length") || 0);
  if (contentLength > MAX_BODY_BYTES) {
    return json({ success: false, message: "Request is too large" }, 413);
  }

  const rawBody = await request.text();
  if (new TextEncoder().encode(rawBody).byteLength > MAX_BODY_BYTES) {
    return json({ success: false, message: "Request is too large" }, 413);
  }

  const signatureHeader = request.headers.get("Calendly-Webhook-Signature") || "";
  const verified = await verifySignature(
    rawBody,
    signatureHeader,
    env.CALENDLY_WEBHOOK_SIGNING_KEY,
  ).catch(() => false);
  if (!verified) {
    return json({ success: false, message: "Invalid webhook signature" }, 401);
  }

  let body: CalendlyWebhookBody;
  try {
    const parsed: unknown = JSON.parse(rawBody);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return json({ success: false, message: "Invalid webhook body" }, 400);
    }
    body = parsed as CalendlyWebhookBody;
  } catch {
    return json({ success: false, message: "Invalid webhook body" }, 400);
  }

  const eventType = clean(body.event, 80);
  if (eventType !== "invitee.created" && eventType !== "invitee.canceled") {
    return json({ success: true, ignored: true });
  }

  const payload = body.payload;
  if (!payload || typeof payload !== "object") {
    return json({ success: false, message: "Missing webhook payload" }, 400);
  }

  const eventUri = getEventUri(payload);
  const inviteeUri = clean(payload.uri, 500);
  if (!eventUri || !inviteeUri.startsWith(CALENDLY_EVENT_PREFIX)) {
    return json({ success: false, message: "Missing Calendly identifiers" }, 400);
  }

  const isRescheduled = payload.rescheduled === true;
  const status = eventType === "invitee.canceled"
    ? (isRescheduled ? "rescheduled" : "cancelled")
    : "webhook_verified";
  const tracking = payload.tracking || {};
  const now = new Date().toISOString();
  const webhookSeenAt = clean(body.created_at, 40) || now;

  try {
    await env.BOOKING_DB.prepare(
      `INSERT INTO booking_attribution (
        calendly_event_uri,
        calendly_invitee_uri,
        webhook_seen_at,
        webhook_event_type,
        status,
        rescheduled,
        old_invitee_uri,
        new_invitee_uri,
        utm_source,
        utm_medium,
        utm_campaign,
        utm_term,
        utm_content,
        created_at,
        updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(calendly_event_uri) DO UPDATE SET
        calendly_invitee_uri = COALESCE(excluded.calendly_invitee_uri, booking_attribution.calendly_invitee_uri),
        webhook_seen_at = excluded.webhook_seen_at,
        webhook_event_type = excluded.webhook_event_type,
        status = excluded.status,
        rescheduled = excluded.rescheduled,
        old_invitee_uri = COALESCE(excluded.old_invitee_uri, booking_attribution.old_invitee_uri),
        new_invitee_uri = COALESCE(excluded.new_invitee_uri, booking_attribution.new_invitee_uri),
        utm_source = COALESCE(excluded.utm_source, booking_attribution.utm_source),
        utm_medium = COALESCE(excluded.utm_medium, booking_attribution.utm_medium),
        utm_campaign = COALESCE(excluded.utm_campaign, booking_attribution.utm_campaign),
        utm_term = COALESCE(excluded.utm_term, booking_attribution.utm_term),
        utm_content = COALESCE(excluded.utm_content, booking_attribution.utm_content),
        updated_at = excluded.updated_at`,
    )
      .bind(
        eventUri,
        inviteeUri,
        webhookSeenAt,
        eventType,
        status,
        isRescheduled ? 1 : 0,
        cleanNullable(payload.old_invitee, 500),
        cleanNullable(payload.new_invitee, 500),
        cleanNullable(tracking.utm_source, 254),
        cleanNullable(tracking.utm_medium, 254),
        cleanNullable(tracking.utm_campaign, 254),
        cleanNullable(tracking.utm_term, 254),
        cleanNullable(tracking.utm_content, 254),
        now,
        now,
      )
      .run();
  } catch {
    return json({ success: false, message: "Booking reconciliation failed" }, 503);
  }

  return json({ success: true, reconciled: true });
}

export const onRequest: PagesFunction<CalendlyWebhookEnv> = async (context) =>
  handleCalendlyWebhook(context.request, context.env);
