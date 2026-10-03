import assert from "node:assert/strict";
import fs from "node:fs";

const source=fs.readFileSync(new URL("../src/index.mjs",import.meta.url),"utf8");
assert.match(source,/event:"kesher_mcp_tool_call"/);
assert.match(source,/tool_name:toolName/);
assert.match(source,/duration_ms:/);
assert.match(source,/error_type:/);
assert.doesNotMatch(source,/console\.log\([^\n]*args/);
assert.doesNotMatch(source,/JSON\.stringify\(args\)/);
for(const forbidden of ["raw_text","child_name","email","phone","diagnosis","medication","medical_history"]){
  const telemetryBlock=source.slice(source.indexOf("const runWithTelemetry"),source.indexOf("function createServer"));
  assert.ok(!telemetryBlock.includes(forbidden),`Telemetry must not log ${forbidden}`);
}
console.log("PASS: Kesher observability logs metadata only, never tool arguments or private fields.");

const wrangler=fs.readFileSync(new URL("../wrangler.jsonc",import.meta.url),"utf8");
assert.match(wrangler,/"name"\s*:\s*"MCP_RATE_LIMITER"/);
assert.match(wrangler,/"limit"\s*:\s*300/);
assert.match(wrangler,/"period"\s*:\s*60/);
console.log("PASS: Kesher staging rate limiter is configured at 300 requests per 60 seconds.");
