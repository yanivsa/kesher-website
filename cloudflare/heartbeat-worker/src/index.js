/**
 * Independent external heartbeat for Kesher Content Pipeline.
 * Runs on Cloudflare's global edge network on a Cron trigger (every 5 minutes)
 * to ensure that the canonical Kesher Content Controller workflow runs even
 * if GitHub Actions internal cron triggers experience delays or outages.
 *
 * Security & Idempotency Guarantees:
 * 1. Health endpoints (/, /health, /ping) are strictly read-only and never dispatch workflows.
 * 2. Manual HTTP dispatch (/dispatch) requires valid Bearer authentication (HEARTBEAT_SECRET).
 * 3. Scheduled events (Cron trigger) execute the dispatch routine with active-run idempotency fencing.
 * 4. Idempotency: Before dispatching, the worker queries GitHub Actions for active runs of the
 *    controller workflow. If a run is currently queued or in-progress, duplicate dispatch is skipped.
 */

export const ACTIVE_RUN_STATUSES = ["queued", "in_progress", "waiting", "pending", "requested"];

export default {
  /**
   * Cloudflare Cron Trigger handler.
   */
  async scheduled(event, env, ctx) {
    const promise = (async () => {
      const result = await handleDispatch(env, {
        source: "cron",
        cron: event.cron,
        scheduledTime: event.scheduledTime,
      });
      console.log(
        JSON.stringify({
          event: "kesher-heartbeat-cron",
          cron: event.cron,
          scheduledTime: event.scheduledTime,
          result,
        })
      );
      return result;
    })();

    if (ctx && typeof ctx.waitUntil === "function") {
      ctx.waitUntil(promise);
    }
    return promise;
  },

  /**
   * HTTP Fetch handler.
   * - GET /, /health, /ping -> Read-only health probe (NO GitHub dispatch).
   * - POST /dispatch, /trigger -> Authenticated manual trigger (Requires Bearer token).
   */
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 1. Read-only health probe routes
    if (request.method === "GET" && (url.pathname === "/" || url.pathname === "/health" || url.pathname === "/ping")) {
      const health = await handleHealthCheck(env);
      return new Response(JSON.stringify(health, null, 2), {
        headers: { "Content-Type": "application/json" },
        status: health.ok ? 200 : 502,
      });
    }

    // 2. Authenticated manual dispatch route
    if (request.method === "POST" && (url.pathname === "/dispatch" || url.pathname === "/trigger")) {
      const authHeader = request.headers.get("Authorization") || "";
      const expectedSecret = env.HEARTBEAT_SECRET || env.DISPATCH_SECRET;

      if (!expectedSecret || !authHeader.startsWith("Bearer ") || authHeader.slice(7).trim() !== expectedSecret.trim()) {
        return new Response(
          JSON.stringify(
            {
              ok: false,
              error: "Unauthorized",
              message: "Valid Bearer token matching HEARTBEAT_SECRET is required for manual dispatch.",
            },
            null,
            2
          ),
          {
            headers: { "Content-Type": "application/json" },
            status: 401,
          }
        );
      }

      const result = await handleDispatch(env, { source: "manual_api" });
      return new Response(JSON.stringify(result, null, 2), {
        headers: { "Content-Type": "application/json" },
        status: result.ok ? 200 : 502,
      });
    }

    return new Response(
      JSON.stringify(
        {
          error: "Not Found",
          message: "Available routes: GET /health (read-only), POST /dispatch (authenticated)",
        },
        null,
        2
      ),
      {
        headers: { "Content-Type": "application/json" },
        status: 404,
      }
    );
  },
};

/**
 * Pure read-only health check.
 * Probes the production site and reports configuration readiness.
 * NEVER mutates state or dispatches GitHub workflows.
 */
export async function handleHealthCheck(env) {
  const siteUrl = env.SITE_URL || "https://kesher.saharoni.com";
  const repo = env.GITHUB_REPO || "yanivsa/kesher-website";
  const workflow = env.WORKFLOW_FILE || "kesher-content-controller.yml";
  const targetRef = env.TARGET_REF || "main";

  const results = {
    worker: "kesher-heartbeat",
    timestamp: new Date().toISOString(),
    status: "healthy",
    ok: true,
    site_health: null,
    dispatch_policy: {
      mode: "scheduled_or_authenticated",
      health_endpoints_read_only: true,
      has_github_token: Boolean(env.GITHUB_TOKEN),
      has_heartbeat_secret: Boolean(env.HEARTBEAT_SECRET || env.DISPATCH_SECRET),
      repo,
      workflow,
      target_ref: targetRef,
    },
  };

  try {
    const res = await fetch(siteUrl, {
      method: "HEAD",
      headers: { "User-Agent": "Kesher-Heartbeat-Health-Probe/1.0" },
    });
    results.site_health = {
      url: siteUrl,
      status: res.status,
      ok: res.ok,
    };
    if (!res.ok) {
      results.ok = false;
      results.status = "degraded";
    }
  } catch (err) {
    results.site_health = {
      url: siteUrl,
      error: err instanceof Error ? err.message : String(err),
      ok: false,
    };
    results.ok = false;
    results.status = "unhealthy";
  }

  return results;
}

/**
 * Checks if the controller workflow currently has active runs.
 * Prevents rapid or duplicate dispatch storms while a controller tick is actively executing.
 */
export async function checkActiveControllerRuns(env) {
  const repo = env.GITHUB_REPO || "yanivsa/kesher-website";
  const workflow = env.WORKFLOW_FILE || "kesher-content-controller.yml";
  const token = env.GITHUB_TOKEN;

  if (!token) {
    return { active: false, active_run: null };
  }

  const endpoint = `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/runs?per_page=5`;
  try {
    const res = await fetch(endpoint, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
        "User-Agent": "Kesher-Cloudflare-Heartbeat/1.0",
      },
    });

    if (!res.ok) {
      console.warn(`[checkActiveControllerRuns] GitHub runs query returned status ${res.status}`);
      return { active: false, active_run: null };
    }

    const data = await res.json();
    const runs = Array.isArray(data?.workflow_runs) ? data.workflow_runs : [];
    const activeRun = runs.find((r) => ACTIVE_RUN_STATUSES.includes(r.status));

    if (activeRun) {
      return {
        active: true,
        active_run: {
          id: activeRun.id,
          status: activeRun.status,
          created_at: activeRun.created_at,
          html_url: activeRun.html_url,
        },
      };
    }
    return { active: false, active_run: null };
  } catch (err) {
    console.warn(`[checkActiveControllerRuns] Failed to query active runs: ${err}`);
    return { active: false, active_run: null };
  }
}

/**
 * Executes workflow dispatch with idempotency protection.
 * Callable only by scheduled cron or authenticated POST /dispatch.
 */
export async function handleDispatch(env, context = {}) {
  const repo = env.GITHUB_REPO || "yanivsa/kesher-website";
  const workflow = env.WORKFLOW_FILE || "kesher-content-controller.yml";
  const targetRef = env.TARGET_REF || "main";
  const token = env.GITHUB_TOKEN;

  const results = {
    timestamp: new Date().toISOString(),
    source: context.source || "unknown",
    ok: true,
    dispatched: false,
    site_probe: null,
    github_dispatch: null,
  };

  // 1. Edge probe of site health
  const siteUrl = env.SITE_URL || "https://kesher.saharoni.com";
  try {
    const res = await fetch(siteUrl, {
      method: "HEAD",
      headers: { "User-Agent": "Kesher-Heartbeat-Probe/1.0" },
    });
    results.site_probe = { status: res.status, ok: res.ok };
  } catch (err) {
    results.site_probe = { error: err instanceof Error ? err.message : String(err), ok: false };
  }

  // 2. Validate token presence
  if (!token) {
    results.ok = false;
    results.github_dispatch = {
      error: "GITHUB_TOKEN_NOT_CONFIGURED",
      message: "Secret GITHUB_TOKEN is not configured on Worker.",
    };
    return results;
  }

  // 3. Idempotency guard: skip dispatch if a controller run is already active
  const { active, active_run } = await checkActiveControllerRuns(env);
  if (active && active_run) {
    results.dispatched = false;
    results.github_dispatch = {
      status: "skipped",
      reason: "controller_already_active",
      active_run,
    };
    return results;
  }

  // 4. Dispatch workflow
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

    if (res.status === 204) {
      results.dispatched = true;
      results.github_dispatch = {
        workflow,
        ref: targetRef,
        status: 204,
        ok: true,
      };
    } else {
      const body = await res.text().catch(() => "");
      results.ok = false;
      results.dispatched = false;
      results.github_dispatch = {
        workflow,
        ref: targetRef,
        status: res.status,
        ok: false,
        response_body: body,
      };
    }
  } catch (err) {
    results.ok = false;
    results.dispatched = false;
    results.github_dispatch = {
      workflow,
      error: err instanceof Error ? err.message : String(err),
      ok: false,
    };
  }

  return results;
}
