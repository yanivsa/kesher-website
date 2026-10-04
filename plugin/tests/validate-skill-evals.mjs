import fs from "node:fs";
import path from "node:path";

const root = path.resolve(new URL("..", import.meta.url).pathname);
const fail = (message) => {
  console.error("FAIL:", message);
  process.exitCode = 1;
};

const manifest = JSON.parse(fs.readFileSync(path.join(root, "plugin.json"), "utf8"));
const pluginName = manifest.name;

const skills = [
  {
    folder: "relationship-conflict",
    skillName: "relationship-conflict",
    tool: "get_conflict_pattern",
  },
  {
    folder: "parenting-guidance",
    skillName: "parenting-guidance",
    tool: "get_parenting_response_plan",
  },
  {
    folder: "parenting-attention-executive-function",
    skillName: "parenting-attention",
    tool: "get_adhd_parenting_plan",
    requireAdhdBoundary: true,
  },
];

for (const skill of skills) {
  const skillPath = path.join(root, "skills", skill.folder, "SKILL.md");
  const agentPath = path.join(root, "skills", skill.folder, "agents", "openai.yaml");
  const source = fs.readFileSync(skillPath, "utf8");

  if (!source.startsWith(`---\nname: ${skill.skillName}\n`)) {
    fail(`${skill.folder}: invalid frontmatter name`);
  }
  if (!source.includes(skill.tool)) fail(`${skill.folder}: expected tool not referenced`);
  if (!/privacy|פרטיות/i.test(source)) fail(`${skill.folder}: missing privacy guidance`);
  if (!/do not|never|לא /i.test(source)) fail(`${skill.folder}: missing explicit negative activation guidance`);

  const identity = `${pluginName}:${skill.skillName}`;
  if (identity.length > 64) {
    fail(`${skill.folder}: plugin:skill identity exceeds 64 characters (${identity.length})`);
  }

  if (!fs.existsSync(agentPath)) {
    fail(`${skill.folder}: missing agents/openai.yaml`);
  } else {
    const agent = fs.readFileSync(agentPath, "utf8");
    if (!/^interface:\s*$/m.test(agent)) fail(`${skill.folder}: missing agent interface`);
    if (!/^\s+display_name:\s*".+"/m.test(agent)) fail(`${skill.folder}: missing display_name`);
    if (!/^\s+short_description:\s*".+"/m.test(agent)) fail(`${skill.folder}: missing short_description`);
    if (!/^\s+default_prompt:\s*".+"/m.test(agent)) fail(`${skill.folder}: missing default_prompt`);
    if (!/^policy:\s*$/m.test(agent)) fail(`${skill.folder}: missing agent policy`);
    if (!/^\s+- CHAT\s*$/m.test(agent)) fail(`${skill.folder}: must target CHAT`);
    if (!/^\s+allow_implicit_invocation:\s*true\s*$/m.test(agent)) {
      fail(`${skill.folder}: implicit invocation must be enabled`);
    }
  }

  if (skill.requireAdhdBoundary) {
    if (!/ADHD/i.test(source) || !/medication|תרופ/i.test(source) || !/diagnos|אבח/i.test(source)) {
      fail(`${skill.folder}: missing ADHD medical boundary`);
    }
  }
}

const data = JSON.parse(fs.readFileSync(path.join(root, "evals/conversation-cases.json"), "utf8"));
const cases = data.cases ?? [];
if (cases.length !== 30) fail(`Expected 30 conversation cases; got ${cases.length}`);

const allowed = new Set([
  "get_conflict_pattern",
  "get_conversation_plan",
  "get_parenting_response_plan",
  "get_adhd_parenting_plan",
  "find_kesher_resource",
]);

for (const conversationCase of cases) {
  if (
    !Array.isArray(conversationCase.messages) ||
    !Array.isArray(conversationCase.expected) ||
    conversationCase.messages.length !== conversationCase.expected.length
  ) {
    fail(`${conversationCase.id}: invalid steps`);
    continue;
  }

  for (const step of conversationCase.expected) {
    if (step.plugin_activation && !allowed.has(step.tool)) {
      fail(`${conversationCase.id}: invalid tool ${step.tool}`);
    }
    if (!step.plugin_activation && step.tool !== null) {
      fail(`${conversationCase.id}: non-activation requires null`);
    }
  }
}

if (!process.exitCode) {
  console.log("PASS: 3 Kesher skills, implicit invocation metadata, and 30 conversation cases are internally consistent.");
}
