import fs from "node:fs";

const golden = JSON.parse(fs.readFileSync(new URL("../evals/golden-prompts.json", import.meta.url), "utf8"));
const contracts = JSON.parse(fs.readFileSync(new URL("../contracts/mcp-tools.v1.json", import.meta.url), "utf8"));
const safety = JSON.parse(fs.readFileSync(new URL("../contracts/safety-boundaries.json", import.meta.url), "utf8"));

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

const forbiddenInputFields = new Set(safety.data_minimization?.forbidden_input_fields ?? []);

for (const tool of tools) {
  if (!tool.description || !/Do not use/i.test(tool.description)) {
    fail(`${tool.name}: description must include explicit exclusions`);
  }
  const a = tool.annotations ?? {};
  for (const key of ["readOnlyHint", "destructiveHint", "openWorldHint", "idempotentHint"]) {
    if (typeof a[key] !== "boolean") fail(`${tool.name}: ${key} must be an explicit boolean`);
  }
  if (a.readOnlyHint !== true) fail(`${tool.name}: V1 tools must be read-only`);
  if (a.destructiveHint !== false) fail(`${tool.name}: V1 tools must be non-destructive`);
  if (a.openWorldHint !== false) fail(`${tool.name}: V1 tools must not access the open world`);
  if (a.idempotentHint !== true) fail(`${tool.name}: V1 tools must be idempotent`);

  const input = tool.inputSchema ?? {};
  if (input.additionalProperties !== false) fail(`${tool.name}: input additionalProperties must be false`);
  const props = input.properties ?? {};
  for (const [field, schema] of Object.entries(props)) {
    if (forbiddenInputFields.has(field)) {
      fail(`${tool.name}: forbidden raw/private input field declared: ${field}`);
    }
    if (schema.type === "string" && !Array.isArray(schema.enum)) {
      fail(`${tool.name}: string input ${field} must be enum-bounded in V1`);
    }
    if (schema.type === "array" && !Array.isArray(schema.items?.enum)) {
      fail(`${tool.name}: array input ${field} must have enum-bounded items in V1`);
    }
  }

  const output = tool.outputSchema ?? {};
  if (output.additionalProperties !== false) fail(`${tool.name}: output additionalProperties must be false`);
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

const requiredExclusions = [
  "crisis_violence",
  "crisis_self_harm",
  "legal_divorce",
  "medical",
  "sexual_health",
  "diagnosis",
  "surveillance",
  "infidelity_surveillance",
  "manipulation"
];
const exclusions = new Set((safety.excluded_intents ?? []).map((item) => item.category));
for (const category of requiredExclusions) {
  if (!exclusions.has(category)) fail(`Safety boundary missing excluded intent: ${category}`);
}
for (const prompt of prompts.filter((p) => requiredExclusions.includes(p.intent_cluster))) {
  if (prompt.expected_plugin_activation !== false) {
    fail(`${prompt.id}: high-risk prompt must not activate V1 plugin`);
  }
}

if (!process.exitCode) {
  console.log("PASS: Phase 2 contracts, safety boundaries, and golden prompts are internally consistent.");
  console.log(`Tools: ${[...names].join(", ")}`);
  console.log(`Prompts: ${prompts.length} total / ${negatives.length} negative`);
  console.log(`Safety exclusions: ${requiredExclusions.length}`);
}
