interface BookingEnv {
  BOOKING_DB?: D1Database;
}

interface BrowserBookingPayload {
  calendly_event_uri?: unknown;
  calendly_invitee_uri?: unknown;
  service_type?: unknown;
  booking_page_path?: unknown;
  landing_page_type?: unknown;
  variant_id?: unknown;
  entry_page_path?: unknown;
  utm_source?: unknown;
  utm_medium?: unknown;
  utm_campaign?: unknown;
  utm_term?: unknown;
  utm_content?: unknown;
  google_click_id_present?: unknown;
  observed_at?: unknown;
}

const MAX_BODY_BYTES = 12_000;
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

const isCalendlyEventUri = (value: string) =>
  value.startsWith(CALENDLY_EVENT_PREFIX) && value.length <= 500;

const isSameOriginRequest = (request: Request) => {
  const origin = request.headers.get("Origin");
  if (!origin) return true;
  try {
    return origin === new URL(request.url).origin;
  } catch {
    return false;
  }
};

export async function handleBrowserBookingConfirmation(
  request: Request,
  env: BookingEnv = {},
) {
  if (request.method !== "POST") {
    return json({ success: false, message: "Method not allowed" }, 405);
  }

  if (!isSameOriginRequest(request)) {
    return json({ success: false, message: "Cross-origin request rejected" }, 403);
  }

  const contentType = request.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return json({ success: false, message: "Expected JSON request" }, 415);
  }

  const contentLength = Number(request.headers.get("content-length") || 0);
  if (contentLength > MAX_BODY_BYTES) {
    return json({ success: false, message: "Request is too large" }, 413);
  }

  let payload: BrowserBookingPayload;
  try {
    const raw = await request.text();
    if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES) {
      return json({ success: false, message: "Request is too large" }, 413);
    }
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return json({ success: false, message: "Invalid JSON request" }, 400);
    }
    payload = parsed as BrowserBookingPayload;
  } catch {
    return json({ success: false, message: "Invalid JSON request" }, 400);
  }

  const eventUri = clean(payload.calendly_event_uri, 500);
  const inviteeUri = clean(payload.calendly_invitee_uri, 500);

  if (!eventUri || !isCalendlyEventUri(eventUri)) {
    return json({ success: false, message: "Invalid Calendly event URI" }, 400);
  }
  if (inviteeUri && !isCalendlyEventUri(inviteeUri)) {
    return json({ success: false, message: "Invalid Calendly invitee URI" }, 400);
  }

  if (!env.BOOKING_DB) {
    return json(
      {
        success: true,
        stored: false,
        message: "Booking observed; reconciliation storage is not configured",
      },
      202,
    );
  }

  const now = new Date().toISOString();
  const observedAt = clean(payload.observed_at, 40) || now;

  try {
    await env.BOOKING_DB.prepare(
      `INSERT INTO booking_attribution (
        calendly_event_uri,
        calendly_invitee_uri,
        browser_seen_at,
        status,
        service_type,
        booking_page_path,
        landing_page_type,
        variant_id,
        entry_page_path,
        utm_source,
        utm_medium,
        utm_campaign,
        utm_term,
        utm_content,
        google_click_id_present,
        created_at,
        updated_at
      ) VALUES (?, ?, ?, 'browser_seen', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(calendly_event_uri) DO UPDATE SET
        calendly_invitee_uri = COALESCE(booking_attribution.calendly_invitee_uri, excluded.calendly_invitee_uri),
        browser_seen_at = COALESCE(booking_attribution.browser_seen_at, excluded.browser_seen_at),
        service_type = COALESCE(booking_attribution.service_type, excluded.service_type),
        booking_page_path = COALESCE(booking_attribution.booking_page_path, excluded.booking_page_path),
        landing_page_type = COALESCE(booking_attribution.landing_page_type, excluded.landing_page_type),
        variant_id = COALESCE(booking_attribution.variant_id, excluded.variant_id),
        entry_page_path = COALESCE(booking_attribution.entry_page_path, excluded.entry_page_path),
        utm_source = COALESCE(booking_attribution.utm_source, excluded.utm_source),
        utm_medium = COALESCE(booking_attribution.utm_medium, excluded.utm_medium),
        utm_campaign = COALESCE(booking_attribution.utm_campaign, excluded.utm_campaign),
        utm_term = COALESCE(booking_attribution.utm_term, excluded.utm_term),
        utm_content = COALESCE(booking_attribution.utm_content, excluded.utm_content),
        google_click_id_present = MAX(booking_attribution.google_click_id_present, excluded.google_click_id_present),
        updated_at = excluded.updated_at`,
    )
      .bind(
        eventUri,
        inviteeUri || null,
        observedAt,
        cleanNullable(payload.service_type, 80),
        cleanNullable(payload.booking_page_path, 300),
        cleanNullable(payload.landing_page_type, 80),
        cleanNullable(payload.variant_id, 20),
        cleanNullable(payload.entry_page_path, 300),
        cleanNullable(payload.utm_source, 254),
        cleanNullable(payload.utm_medium, 254),
        cleanNullable(payload.utm_campaign, 254),
        cleanNullable(payload.utm_term, 254),
        cleanNullable(payload.utm_content, 254),
        payload.google_click_id_present === true ? 1 : 0,
        now,
        now,
      )
      .run();
  } catch {
    return json({ success: false, message: "Booking storage unavailable" }, 503);
  }

  return json({ success: true, stored: true });
}

export const onRequest: PagesFunction<BookingEnv> = async (context) =>
  handleBrowserBookingConfirmation(context.request, context.env);
