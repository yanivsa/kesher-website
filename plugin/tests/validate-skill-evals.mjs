import fs from "node:fs";
import path from "node:path";
const root=path.resolve(new URL("..",import.meta.url).pathname);
const fail=(m)=>{console.error("FAIL:",m);process.exitCode=1;};
const skills=[
 ["relationship-conflict","get_conflict_pattern"],
 ["parenting-guidance","get_parenting_response_plan"],
 ["parenting-attention-executive-function","get_adhd_parenting_plan"]
];
for(const [name,tool] of skills){
  const p=path.join(root,"skills",name,"SKILL.md");
  const s=fs.readFileSync(p,"utf8");
  if(!s.startsWith(`---\nname: ${name}\n`)) fail(`${name}: invalid frontmatter`);
  if(!s.includes(tool)) fail(`${name}: expected tool not referenced`);
  if(!/privacy|פרטיות/i.test(s)) fail(`${name}: missing privacy guidance`);
  if(!/do not|never|לא /i.test(s)) fail(`${name}: missing explicit negative activation guidance`);
  if(name==="parenting-attention-executive-function"){
    if(!/ADHD/i.test(s)||!/medication|תרופ/i.test(s)||!/diagnos|אבח/i.test(s)) fail(`${name}: missing ADHD medical boundary`);
  }
}
const data=JSON.parse(fs.readFileSync(path.join(root,"evals/conversation-cases.json"),"utf8"));
const cases=data.cases??[];
if(cases.length!==30) fail(`Expected 30 conversation cases; got ${cases.length}`);
const allowed=new Set(["get_conflict_pattern","get_conversation_plan","get_parenting_response_plan","get_adhd_parenting_plan","find_kesher_resource"]);
for(const c of cases){
  if(!Array.isArray(c.messages)||!Array.isArray(c.expected)||c.messages.length!==c.expected.length) fail(`${c.id}: invalid steps`);
  for(const step of c.expected){
    if(step.plugin_activation&&!allowed.has(step.tool)) fail(`${c.id}: invalid tool ${step.tool}`);
    if(!step.plugin_activation&&step.tool!==null) fail(`${c.id}: non-activation requires null`);
  }
}
if(!process.exitCode) console.log("PASS: 3 Kesher skills and 30 conversation cases are internally consistent.");
