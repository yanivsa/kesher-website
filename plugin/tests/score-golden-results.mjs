import fs from "node:fs";
import path from "node:path";

const here = path.dirname(new URL(import.meta.url).pathname);
const goldenPath = path.resolve(here, "../evals/golden-prompts.json");
const golden = JSON.parse(fs.readFileSync(goldenPath, "utf8"));
const byId = new Map(golden.prompts.map((p) => [p.id, p]));

const arg = process.argv[2];
let results;

if (arg === "--self-test") {
  results = golden.prompts.map((p) => ({
    id: p.id,
    actual_plugin_activation: p.expected_plugin_activation,
    actual_tool: p.expected_tool
  }));
} else {
  if (!arg) {
    console.error("Usage: node plugin/tests/score-golden-results.mjs <results.json> | --self-test");
    process.exit(2);
  }
  const file = JSON.parse(fs.readFileSync(path.resolve(arg), "utf8"));
  results = file.results ?? [];
}

if (results.length !== golden.prompts.length) {
  console.error(`Expected ${golden.prompts.length} results; got ${results.length}`);
  process.exit(1);
}

const seen = new Set();
let tp = 0;
let fp = 0;
let fn = 0;
let tn = 0;
let toolCorrect = 0;
let toolEligible = 0;
const failures = [];

for (const result of results) {
  if (seen.has(result.id)) {
    console.error(`Duplicate result id: ${result.id}`);
    process.exit(1);
  }
  seen.add(result.id);
  const expected = byId.get(result.id);
  if (!expected) {
    console.error(`Unknown result id: ${result.id}`);
    process.exit(1);
  }

  const actualActive = result.actual_plugin_activation === true;
  const expectedActive = expected.expected_plugin_activation === true;

  if (expectedActive && actualActive) tp++;
  else if (!expectedActive && actualActive) fp++;
  else if (expectedActive && !actualActive) fn++;
  else tn++;

  if (expectedActive) {
    toolEligible++;
    if (actualActive && result.actual_tool === expected.expected_tool) toolCorrect++;
  }

  if (actualActive !== expectedActive || (expectedActive && result.actual_tool !== expected.expected_tool)) {
    failures.push({
      id: expected.id,
      bucket: expected.bucket,
      expected_activation: expectedActive,
      actual_activation: actualActive,
      expected_tool: expected.expected_tool,
      actual_tool: result.actual_tool ?? null
    });
  }
}

const precision = tp + fp === 0 ? 0 : tp / (tp + fp);
const recall = tp + fn === 0 ? 0 : tp / (tp + fn);
const specificity = tn + fp === 0 ? 0 : tn / (tn + fp);
const toolAccuracy = toolEligible === 0 ? 0 : toolCorrect / toolEligible;

const summary = {
  total: results.length,
  confusion_matrix: {tp, fp, fn, tn},
  precision,
  recall,
  specificity,
  expected_tool_accuracy: toolAccuracy,
  thresholds: {
    precision: 0.90,
    recall: 0.70,
    negative_false_positives: 0
  },
  pass: precision >= 0.90 && recall >= 0.70 && fp === 0,
  failures
};

console.log(JSON.stringify(summary, null, 2));
if (!summary.pass) process.exitCode = 1;
