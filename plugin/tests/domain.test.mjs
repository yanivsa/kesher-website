import assert from "node:assert/strict";
import { getConflictPattern, getConversationPlan } from "../src/domain.mjs";

const pattern = getConflictPattern({
  topic: "money",
  interaction_signals: ["criticism","defensiveness","repetition"],
  goal: "understand_pattern"
});
assert.equal(pattern.pattern_label_he, "ביקורת–התגוננות");
assert.match(pattern.summary_he, /כסף/);
assert.ok(pattern.cycle_steps_he.length >= 2);
assert.ok(pattern.avoid_he.length >= 1);

const pursueWithdraw = getConflictPattern({
  topic: "recurring_other",
  interaction_signals: ["pursuit","withdrawal"],
  goal: "restart_conversation"
});
assert.equal(pursueWithdraw.pattern_label_he, "לחץ–התרחקות");

const plan = getConversationPlan({
  topic: "household",
  goal: "discuss_household",
  emotional_intensity: "high",
  interaction_risk: "escalation",
  tone: "gentle"
});
assert.match(plan.opening_he, /חלוקת עומס/);
assert.ok(plan.steps_he.length >= 3 && plan.steps_he.length <= 5);
assert.match(plan.pause_phrase_he, /השיחה/);
assert.equal(plan.avoid_phrases_he.length, 4);

assert.throws(
  () => getConflictPattern({topic:"money",interaction_signals:["narcissism"],goal:"understand_pattern"}),
  /Invalid interaction_signals/
);
assert.throws(
  () => getConversationPlan({topic:"money",goal:"force_compliance",emotional_intensity:"high",interaction_risk:"none",tone:"direct"}),
  /Invalid goal/
);

console.log("PASS: Kesher domain logic tests.");
