interface TurnstileConfigEnv {
  TURNSTILE_SITE_KEY?: string;
}

const json = (body: object, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });

export const onRequestGet: PagesFunction<TurnstileConfigEnv> = async (context) => {
  const siteKey = context.env.TURNSTILE_SITE_KEY?.trim();
  if (!siteKey) {
    return json({ success: false, message: "Security verification is not configured" }, 503);
  }
  return json({ success: true, siteKey });
};

export const onRequest: PagesFunction<TurnstileConfigEnv> = async (context) => {
  if (context.request.method !== "GET") {
    return json({ success: false, message: "Method not allowed" }, 405);
  }
  return onRequestGet(context);
};
