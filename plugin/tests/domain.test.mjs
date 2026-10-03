import assert from "node:assert/strict";
import {
  getConflictPattern,
  getConversationPlan,
  getParentingResponsePlan,
  getAdhdParentingPlan,
  findKesherResource
} from "../src/domain.mjs";

const pattern=getConflictPattern({topic:"money",interaction_signals:["criticism","defensiveness","repetition"],goal:"understand_pattern"});
assert.equal(pattern.pattern_label_he,"ביקורת–התגוננות");

const plan=getConversationPlan({topic:"household",goal:"discuss_household",emotional_intensity:"high",interaction_risk:"escalation",tone:"gentle"});
assert.match(plan.opening_he,/חלוקת עומס/);

const parenting=getParentingResponsePlan({age_band:"unknown",challenge:"screens",goal:"set_boundary",response_style:"firm_kind"});
assert.match(parenting.framing_he,/מסכ/);
assert.ok(parenting.steps_he.length>=3);

const adhd=getAdhdParentingPlan({age_band:"unknown",challenge:"task_initiation",goal:"start_task",support_level:"structured"});
assert.match(adhd.executive_function_frame_he,/התחל|משימה|תפקוד/);
assert.ok(adhd.environment_adjustments_he.length>=2);

const resources=findKesherResource({domain:"parenting_adhd",topic:"adhd_morning",content_type:"article"});
assert.ok(Array.isArray(resources.resources));
assert.ok(resources.resources.length>=1);
assert.ok(resources.resources.every(r=>r.url.startsWith("https://kesher.saharoni.com/")));

for (const fn of [
  ()=>getConflictPattern({topic:"money",interaction_signals:["criticism"],goal:"understand_pattern",raw_text:"private"}),
  ()=>getConversationPlan({topic:"household",goal:"discuss_household",emotional_intensity:"moderate",interaction_risk:"none",tone:"gentle",email:"private@example.com"}),
  ()=>getParentingResponsePlan({age_band:"elementary",challenge:"screens",goal:"set_boundary",response_style:"firm_kind",child_name:"Dana"}),
  ()=>getAdhdParentingPlan({age_band:"elementary",challenge:"organization",goal:"increase_independence",support_level:"structured",diagnosis:"ADHD"}),
  ()=>findKesherResource({domain:"parenting",topic:"screens",content_type:"article",raw_text:"private"})
]) assert.throws(fn,/Unexpected field/);

console.log("PASS: Kesher V2 domain logic tests.");
