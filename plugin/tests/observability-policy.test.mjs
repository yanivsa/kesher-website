import assert from "node:assert/strict";
import fs from "node:fs";

const source=fs.readFileSync(new URL("../src/index.mjs",import.meta.url),"utf8");
assert.doesNotMatch(source,/console\.log\(/,"Read-only MCP tools must not emit custom operational logs.");
assert.doesNotMatch(source,/runWithTelemetry/,"Read-only MCP tools must not wrap calls in state-writing telemetry.");
console.log("PASS: Kesher tool handlers do not write custom logs, preserving readOnlyHint=true.");

const wrangler=fs.readFileSync(new URL("../wrangler.jsonc",import.meta.url),"utf8");
assert.match(wrangler,/"observability"\s*:\s*\{/);
assert.match(wrangler,/"name"\s*:\s*"MCP_RATE_LIMITER"/);
assert.match(wrangler,/"limit"\s*:\s*300/);
assert.match(wrangler,/"period"\s*:\s*60/);
console.log("PASS: Cloudflare infrastructure observability and staging rate limiting are configured.");
