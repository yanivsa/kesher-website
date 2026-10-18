import { describe, it, expect, vi, beforeEach } from "vitest";
import worker, {
  handleHealthCheck,
  handleDispatch,
  checkActiveControllerRuns,
} from "../cloudflare/heartbeat-worker/src/index.js";

type MockExecutionContext = {
  waitUntil: (promise: Promise<unknown>) => void;
  passThroughOnException?: () => void;
};

const createMockCtx = (waitUntilFn?: (promise: Promise<unknown>) => void): MockExecutionContext => ({
  waitUntil: waitUntilFn || vi.fn(),
});

describe("Cloudflare Heartbeat Worker", () => {
  const defaultEnv = {
    SITE_URL: "https://kesher.saharoni.com",
    GITHUB_REPO: "yanivsa/kesher-website",
    WORKFLOW_FILE: "kesher-content-controller.yml",
    TARGET_REF: "main",
    GITHUB_TOKEN: "mock-gh-token-12345",
    HEARTBEAT_SECRET: "mock-heartbeat-secret-xyz",
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("Security: Health endpoints must be read-only", () => {
    it("GET /health returns 200 with health probe and NEVER calls GitHub dispatch", async () => {
      const fetchMock = vi.fn().mockImplementation((url: string) => {
        if (url === "https://kesher.saharoni.com") {
          return Promise.resolve(new Response(null, { status: 200 }));
        }
        throw new Error(`Unexpected fetch to ${url}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const request = new Request("https://worker.local/health", { method: "GET" });
      const response = await worker.fetch(request, defaultEnv, createMockCtx());

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.status).toBe("healthy");
      expect(data.ok).toBe(true);
      expect(data.dispatch_policy.health_endpoints_read_only).toBe(true);

      // Verify only the site was probed, NO GitHub API was ever called
      expect(fetchMock).toHaveBeenCalledTimes(1);
      expect(fetchMock).toHaveBeenCalledWith("https://kesher.saharoni.com", expect.anything());
    });

    it("GET / and GET /ping also behave as read-only probes", async () => {
      const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
      vi.stubGlobal("fetch", fetchMock);

      for (const path of ["/", "/ping"]) {
        const req = new Request(`https://worker.local${path}`, { method: "GET" });
        const res = await worker.fetch(req, defaultEnv, createMockCtx());
        expect(res.status).toBe(200);
        const data = await res.json();
        expect(data.ok).toBe(true);
      }
      expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    it("Reports degraded status when site probe returns 500", async () => {
      const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 500 }));
      vi.stubGlobal("fetch", fetchMock);

      const request = new Request("https://worker.local/health", { method: "GET" });
      const response = await worker.fetch(request, defaultEnv, createMockCtx());

      expect(response.status).toBe(502);
      const data = await response.json();
      expect(data.status).toBe("degraded");
      expect(data.ok).toBe(false);
    });
  });

  describe("Security: Manual HTTP dispatch requires valid Bearer authentication", () => {
    it("POST /dispatch returns 401 when Authorization header is missing", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const request = new Request("https://worker.local/dispatch", { method: "POST" });
      const response = await worker.fetch(request, defaultEnv, createMockCtx());

      expect(response.status).toBe(401);
      const data = await response.json();
      expect(data.error).toBe("Unauthorized");
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("POST /dispatch returns 401 when Bearer token is invalid", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);

      const request = new Request("https://worker.local/dispatch", {
        method: "POST",
        headers: { Authorization: "Bearer wrong-secret" },
      });
      const response = await worker.fetch(request, defaultEnv, createMockCtx());

      expect(response.status).toBe(401);
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("POST /dispatch succeeds with valid Bearer token", async () => {
      const fetchMock = vi.fn().mockImplementation((url: string) => {
        if (url === "https://kesher.saharoni.com") {
          return Promise.resolve(new Response(null, { status: 200 }));
        }
        if (url.includes("/actions/workflows/kesher-content-controller.yml/runs")) {
          return Promise.resolve(new Response(JSON.stringify({ workflow_runs: [] }), { status: 200 }));
        }
        if (url.includes("/actions/workflows/kesher-content-controller.yml/dispatches")) {
          return Promise.resolve(new Response(null, { status: 204 }));
        }
        throw new Error(`Unexpected fetch to ${url}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const request = new Request("https://worker.local/dispatch", {
        method: "POST",
        headers: { Authorization: "Bearer mock-heartbeat-secret-xyz" },
      });
      const response = await worker.fetch(request, defaultEnv, createMockCtx());

      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data.dispatched).toBe(true);
      expect(data.github_dispatch.status).toBe(204);
    });
  });

  describe("Scheduled Cron: Dispatch and Idempotency Fencing", () => {
    it("Dispatches controller when no runs are active", async () => {
      const fetchCalls: Array<{ url: string; opts?: RequestInit }> = [];
      const fetchMock = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
        fetchCalls.push({ url, opts });
        if (url === "https://kesher.saharoni.com") {
          return Promise.resolve(new Response(null, { status: 200 }));
        }
        if (url.includes("/runs")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                workflow_runs: [
                  { id: 111, status: "completed", conclusion: "success" },
                ],
              }),
              { status: 200 }
            )
          );
        }
        if (url.includes("/dispatches")) {
          return Promise.resolve(new Response(null, { status: 204 }));
        }
        throw new Error(`Unexpected fetch to ${url}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const waitUntil = vi.fn((_p: Promise<unknown>) => {});
      await worker.scheduled(
        { cron: "*/5 * * * *", scheduledTime: Date.now() },
        defaultEnv,
        createMockCtx(waitUntil)
      );

      const dispatchCall = fetchCalls.find((c) => c.url.includes("/dispatches"));
      expect(dispatchCall).toBeDefined();
      expect(dispatchCall!.opts?.method).toBe("POST");
      expect(
        (dispatchCall!.opts?.headers as Record<string, string>)?.Authorization
      ).toBe("Bearer mock-gh-token-12345");
      expect(JSON.parse(String(dispatchCall!.opts?.body))).toEqual({ ref: "main" });
    });

    it("Idempotency: Skips dispatch when a controller run is already active (in_progress)", async () => {
      const fetchCalls: Array<{ url: string; opts?: RequestInit }> = [];
      const fetchMock = vi.fn().mockImplementation((url: string, opts?: RequestInit) => {
        fetchCalls.push({ url, opts });
        if (url === "https://kesher.saharoni.com") {
          return Promise.resolve(new Response(null, { status: 200 }));
        }
        if (url.includes("/runs")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                workflow_runs: [
                  {
                    id: 999999,
                    status: "in_progress",
                    created_at: "2026-10-16T12:00:00Z",
                    html_url: "https://github.com/yanivsa/kesher-website/actions/runs/999999",
                  },
                ],
              }),
              { status: 200 }
            )
          );
        }
        if (url.includes("/dispatches")) {
          return Promise.resolve(new Response(null, { status: 204 }));
        }
        throw new Error(`Unexpected fetch to ${url}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await handleDispatch(defaultEnv, { source: "cron" });

      expect(result.dispatched).toBe(false);
      expect(result.github_dispatch.status).toBe("skipped");
      expect(result.github_dispatch.reason).toBe("controller_already_active");
      expect(result.github_dispatch.active_run.id).toBe(999999);

      // Verify dispatch endpoint was NOT called
      const dispatchCall = fetchCalls.find((c) => c.url.includes("/dispatches"));
      expect(dispatchCall).toBeUndefined();
    });

    it("Idempotency: Skips dispatch when a controller run is queued", async () => {
      const fetchMock = vi.fn().mockImplementation((url: string) => {
        if (url === "https://kesher.saharoni.com") {
          return Promise.resolve(new Response(null, { status: 200 }));
        }
        if (url.includes("/runs")) {
          return Promise.resolve(
            new Response(
              JSON.stringify({
                workflow_runs: [{ id: 888888, status: "queued" }],
              }),
              { status: 200 }
            )
          );
        }
        return Promise.resolve(new Response(null, { status: 200 }));
      });
      vi.stubGlobal("fetch", fetchMock);

      const result = await handleDispatch(defaultEnv, { source: "cron" });
      expect(result.dispatched).toBe(false);
      expect(result.github_dispatch.reason).toBe("controller_already_active");
    });

    it("Fails safely when GITHUB_TOKEN is not configured", async () => {
      const envWithoutToken = { ...defaultEnv, GITHUB_TOKEN: "" };
      const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
      vi.stubGlobal("fetch", fetchMock);

      const result = await handleDispatch(envWithoutToken, { source: "cron" });
      expect(result.ok).toBe(false);
      expect(result.dispatched).toBe(false);
      expect(result.github_dispatch.error).toBe("GITHUB_TOKEN_NOT_CONFIGURED");
    });
  });

  describe("Helper Functions", () => {
    it("handleHealthCheck runs site probe directly", async () => {
      const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
      vi.stubGlobal("fetch", fetchMock);

      const result = await handleHealthCheck(defaultEnv);
      expect(result.ok).toBe(true);
      expect(result.status).toBe("healthy");
    });

    it("checkActiveControllerRuns detects active runs", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            workflow_runs: [{ id: 777, status: "in_progress" }],
          }),
          { status: 200 }
        )
      );
      vi.stubGlobal("fetch", fetchMock);

      const result = await checkActiveControllerRuns(defaultEnv);
      expect(result.active).toBe(true);
      expect(result.active_run?.id).toBe(777);
    });
  });
});
