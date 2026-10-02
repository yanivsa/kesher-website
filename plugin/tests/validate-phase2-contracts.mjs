import fs from "node:fs";

const golden = JSON.parse(fs.readFileSync(new URL("../evals/golden-prompts.json", import.meta.url), "utf8"));
const contracts = JSON.parse(fs.readFileSync(new URL("../contracts/mcp-tools.v1.json", import.meta.url), "utf8"));

const fail = (message) => {
  console.error("FAIL:", message);
  process.exitCode = 1;
};

const tools = contracts.tools ?? [];
if (tools.length !== 2) fail(`Expected exactly 2 V1 public tools; got ${tools.length}`);

const names = new Set(tools.map((tool) => tool.name));
for (const expected of ["get_conflict_pattern", "get_conversation_plan"]) {
  if (!names.has(expected)) fail(`Missing expected tool: ${expected}`);
}

for (const tool of tools) {
  if (!tool.description || !/Do not use/i.test(tool.description)) {
    fail(`${tool.name}: description must include explicit exclusions`);
  }
  const a = tool.annotations ?? {};
  for (const key of ["readOnlyHint", "destructiveHint", "openWorldHint"]) {
    if (typeof a[key] !== "boolean") fail(`${tool.name}: ${key} must be an explicit boolean`);
  }
  if (a.readOnlyHint !== true) fail(`${tool.name}: V1 tools must be read-only`);
  if (a.destructiveHint !== false) fail(`${tool.name}: V1 tools must be non-destructive`);
  if (a.openWorldHint !== false) fail(`${tool.name}: V1 tools must not access the open world`);

  const input = tool.inputSchema ?? {};
  if (input.additionalProperties !== false) fail(`${tool.name}: input additionalProperties must be false`);
  const props = input.properties ?? {};
  for (const [field, schema] of Object.entries(props)) {
    if (schema.type === "string" && !Array.isArray(schema.enum)) {
      fail(`${tool.name}: string input ${field} must be enum-bounded in V1`);
    }
    if (schema.type === "array" && !Array.isArray(schema.items?.enum)) {
      fail(`${tool.name}: array input ${field} must have enum-bounded items in V1`);
    }
  }
}

const prompts = golden.prompts ?? [];
if (prompts.length !== 100) fail(`Expected 100 golden prompts; got ${prompts.length}`);
if (new Set(prompts.map((p) => p.prompt)).size !== prompts.length) fail("Golden prompts must be unique");

for (const prompt of prompts) {
  if (prompt.expected_plugin_activation) {
    if (!names.has(prompt.expected_tool)) fail(`${prompt.id}: positive prompt routes to unknown tool ${prompt.expected_tool}`);
  } else if (prompt.expected_tool !== null) {
    fail(`${prompt.id}: negative prompt must have expected_tool=null`);
  }
}

const negatives = prompts.filter((p) => p.bucket === "negative");
if (negatives.length !== 30) fail(`Expected 30 negative prompts; got ${negatives.length}`);
if (!negatives.every((p) => p.expected_plugin_activation === false)) fail("Every negative prompt must disable plugin activation");

if (!process.exitCode) {
  console.log("PASS: Phase 2 contracts and golden prompts are internally consistent.");
  console.log(`Tools: ${[...names].join(", ")}`);
  console.log(`Prompts: ${prompts.length} total / ${negatives.length} negative`);
}
