/**
 * Independent external heartbeat for Kesher Content Pipeline.
 * Runs on Cloudflare's global edge network on a Cron trigger (every 5 minutes)
 * to ensure that the canonical Kesher Content Controller workflow runs even
 * if GitHub Actions internal cron triggers experience delays or outages.
 */

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(
      (async () => {
        const result = await handleHeartbeat(env);
        console.log(
          JSON.stringify({
            event: "kesher-heartbeat",
            cron: event.cron,
            scheduledTime: event.scheduledTime,
            result,
          })
        );
      })()
    );
  },

  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/" || url.pathname === "/health" || url.pathname === "/ping") {
      const result = await handleHeartbeat(env);
      return new Response(JSON.stringify(result, null, 2), {
        headers: { "Content-Type": "application/json" },
        status: result.ok ? 200 : 502,
      });
    }
    return new Response("Not Found", { status: 404 });
  },
};

async function handleHeartbeat(env) {
  const repo = env.GITHUB_REPO || "yanivsa/kesher-website";
  const workflow = env.WORKFLOW_FILE || "kesher-content-controller.yml";
  const livenessWorkflow = env.LIVENESS_WORKFLOW_FILE || "kesher-controller-liveness.yml";
  const targetRef = env.TARGET_REF || "main";
  const siteUrl = env.SITE_URL || "https://kesher.saharoni.com";
  const token = env.GITHUB_TOKEN;

  const results = {
    timestamp: new Date().toISOString(),
    site_health: null,
    github_dispatch: null,
    ok: true,
  };

  // 1. Probe production site health
  try {
    const res = await fetch(siteUrl, {
      method: "HEAD",
      headers: { "User-Agent": "Kesher-Heartbeat-Probe/1.0" },
    });
    results.site_health = {
      url: siteUrl,
      status: res.status,
      ok: res.ok,
    };
    if (!res.ok) {
      results.ok = false;
    }
  } catch (err) {
    results.site_health = {
      url: siteUrl,
      error: err instanceof Error ? err.message : String(err),
      ok: false,
    };
    results.ok = false;
  }

  // 2. Dispatch GitHub Actions workflow if token is available
  if (token) {
    const dispatchEndpoint = `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`;
    try {
      const res = await fetch(dispatchEndpoint, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github.v3+json",
          "User-Agent": "Kesher-Cloudflare-Heartbeat/1.0",
        },
        body: JSON.stringify({ ref: targetRef }),
      });
      results.github_dispatch = {
        workflow,
        ref: targetRef,
        status: res.status,
        ok: res.status === 204,
      };
      if (res.status !== 204) {
        results.github_dispatch.body = await res.text().catch(() => "");
        results.ok = false;
      }
    } catch (err) {
      results.github_dispatch = {
        workflow,
        error: err instanceof Error ? err.message : String(err),
        ok: false,
      };
      results.ok = false;
    }
  } else {
    results.github_dispatch = {
      note: "GITHUB_TOKEN not configured; edge probe only",
      ok: true,
    };
  }

  return results;
}
