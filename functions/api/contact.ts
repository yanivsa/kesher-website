interface ContactEnv {
  FORMSPREE_ENDPOINT?: string;
  TURNSTILE_SECRET_KEY?: string;
}

interface ContactPayload {
  kind?: "contact" | "lead_magnet";
  name?: string;
  email?: string;
  phone?: string;
  service?: string;
  message?: string;
  company?: string;
  startedAt?: number;
  turnstileToken?: string;
}

const DEFAULT_FORMSPREE_ENDPOINT = "https://formspree.io/f/xvgzgeyw";
const MAX_BODY_BYTES = 20_000;
const MIN_FORM_TIME_MS = 1_500;

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

const isEmail = (value: string) =>
  /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

const isPhone = (value: string) =>
  /^[+()\d\s-]{7,20}$/.test(value);

const verifyTurnstile = async (
  secret: string,
  token: string,
  remoteIp: string | null,
) => {
  const body = new FormData();
  body.set("secret", secret);
  body.set("response", token);
  if (remoteIp) body.set("remoteip", remoteIp);

  const response = await fetch(
    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    { method: "POST", body },
  );
  const result = (await response.json()) as { success?: boolean };
  return result.success === true;
};

export async function handleContactRequest(
  request: Request,
  env: ContactEnv = {},
) {
  if (request.method !== "POST") {
    return json({ success: false, message: "Method not allowed" }, 405);
  }

  const contentType = request.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    return json({ success: false, message: "Expected JSON request" }, 415);
  }

  const contentLength = Number(request.headers.get("content-length") || 0);
  if (contentLength > MAX_BODY_BYTES) {
    return json({ success: false, message: "Request is too large" }, 413);
  }

  let raw: ContactPayload;
  try {
    const body = await request.text();
    if (new TextEncoder().encode(body).byteLength > MAX_BODY_BYTES) {
      return json({ success: false, message: "Request is too large" }, 413);
    }
    const parsed: unknown = JSON.parse(body);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return json({ success: false, message: "Invalid JSON request" }, 400);
    }
    raw = parsed as ContactPayload;
  } catch {
    return json({ success: false, message: "Invalid JSON request" }, 400);
  }

  if (clean(raw.company, 200)) {
    return json({ success: true, message: "Request received" });
  }

  const startedAt = Number(raw.startedAt || 0);
  if (!startedAt || Date.now() - startedAt < MIN_FORM_TIME_MS) {
    return json({ success: false, message: "Please try again" }, 429);
  }

  const payload = {
    kind: raw.kind === "lead_magnet" ? "lead_magnet" : "contact",
    name: clean(raw.name, 100),
    email: clean(raw.email, 254).toLowerCase(),
    phone: clean(raw.phone, 30),
    service: clean(raw.service, 60),
    message: clean(raw.message, 2_000),
  };

  if (!isEmail(payload.email)) {
    return json({ success: false, message: "Invalid email address" }, 400);
  }
  if (
    payload.kind === "contact" &&
    (!payload.name || !isPhone(payload.phone))
  ) {
    return json({ success: false, message: "Invalid contact details" }, 400);
  }

  if (env.TURNSTILE_SECRET_KEY) {
    if (!raw.turnstileToken) {
      return json({ success: false, message: "Verification is required" }, 400);
    }
    let verified: boolean;
    try {
      verified = await verifyTurnstile(
        env.TURNSTILE_SECRET_KEY,
        raw.turnstileToken,
        request.headers.get("CF-Connecting-IP"),
      );
    } catch {
      return json(
        { success: false, message: "Verification service is unavailable" },
        503,
      );
    }
    if (!verified) {
      return json({ success: false, message: "Verification failed" }, 403);
    }
  }

  let providerResponse: Response;
  try {
    providerResponse = await fetch(
      env.FORMSPREE_ENDPOINT || DEFAULT_FORMSPREE_ENDPOINT,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          ...payload,
          _subject:
            payload.kind === "lead_magnet"
              ? "בקשה להורדת מדריך מהאתר"
              : `פנייה חדשה מהאתר: ${payload.name}`,
        }),
      },
    );
  } catch {
    return json(
      { success: false, message: "The message provider is unavailable" },
      502,
    );
  }

  if (!providerResponse.ok) {
    return json(
      { success: false, message: "The message provider rejected the request" },
      502,
    );
  }

  return json({
    success: true,
    message: "Request delivered",
    ...(payload.kind === "lead_magnet"
      ? { downloadUrl: "/guides/5-sentences-stop-an-argument.html" }
      : {}),
  });
}

export const onRequest: PagesFunction<ContactEnv> = async (context) =>
  handleContactRequest(context.request, context.env);
