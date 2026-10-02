import fs from "node:fs";
import path from "node:path";

const root = path.resolve(new URL("..", import.meta.url).pathname);
const skillPath = path.join(root, "skills/relationship-conflict/SKILL.md");
const casesPath = path.join(root, "evals/conversation-cases.json");

const skill = fs.readFileSync(skillPath, "utf8");
const data = JSON.parse(fs.readFileSync(casesPath, "utf8"));
const fail = (message) => {
  console.error("FAIL:", message);
  process.exitCode = 1;
};

if (!skill.startsWith("---\nname: relationship-conflict\n")) fail("Skill frontmatter/name is invalid");
if (!/Do not use for crisis/i.test(skill)) fail("Skill description must state exclusions");
if (!/Never send a raw relationship story/i.test(skill)) fail("Skill must enforce data minimization");
if (!/No promotional CTA/i.test(skill)) fail("Skill must prohibit promotional conversion behavior");

const cases = data.cases ?? [];
if (cases.length !== 20) fail(`Expected 20 conversation cases; got ${cases.length}`);
if (new Set(cases.map((c) => c.id)).size !== cases.length) fail("Conversation case IDs must be unique");

const followups = cases.filter((c) => c.type === "follow_up");
const boundaries = cases.filter((c) => c.type === "boundary");
if (followups.length !== 10) fail(`Expected 10 follow-up cases; got ${followups.length}`);
if (boundaries.length !== 10) fail(`Expected 10 boundary cases; got ${boundaries.length}`);

for (const c of cases) {
  if (!Array.isArray(c.messages) || c.messages.length < 1) fail(`${c.id}: missing messages`);
  if (!Array.isArray(c.expected) || c.expected.length !== c.messages.length) fail(`${c.id}: expected steps must match messages`);
  for (const step of c.expected) {
    if (step.plugin_activation) {
      if (!["get_conflict_pattern","get_conversation_plan"].includes(step.tool)) fail(`${c.id}: invalid expected tool`);
    } else if (step.tool !== null) {
      fail(`${c.id}: non-activation step must use tool=null`);
    }
  }
}
if (!boundaries.every((c) => c.expected.every((s) => s.plugin_activation === false))) {
  fail("Every boundary case must expect no Kesher activation");
}

if (!process.exitCode) {
  console.log("PASS: Kesher skill and 20 multi-turn/boundary eval cases are internally consistent.");
}
