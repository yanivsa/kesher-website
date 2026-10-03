import fs from "node:fs";
const golden=JSON.parse(fs.readFileSync(new URL("../evals/golden-prompts.json",import.meta.url),"utf8"));
const contracts=JSON.parse(fs.readFileSync(new URL("../contracts/mcp-tools.v2.json",import.meta.url),"utf8"));
const safety=JSON.parse(fs.readFileSync(new URL("../contracts/safety-boundaries.json",import.meta.url),"utf8"));
const fail=(m)=>{console.error("FAIL:",m);process.exitCode=1;};
const expected=["get_conflict_pattern","get_conversation_plan","get_parenting_response_plan","get_adhd_parenting_plan","find_kesher_resource"];
const tools=contracts.tools??[];
if(tools.length!==5) fail(`Expected 5 V2 tools; got ${tools.length}`);
const names=new Set(tools.map(t=>t.name));
for(const n of expected) if(!names.has(n)) fail(`Missing ${n}`);
const forbidden=new Set(safety.data_minimization?.forbidden_input_fields??[]);
for(const tool of tools){
  if(!tool.description||!/Do not use/i.test(tool.description)) fail(`${tool.name}: missing negative selection guidance`);
  const a=tool.annotations??{};
  if(a.readOnlyHint!==true||a.destructiveHint!==false||a.openWorldHint!==false||a.idempotentHint!==true) fail(`${tool.name}: invalid annotations`);
  if(tool.inputSchema?.additionalProperties!==false) fail(`${tool.name}: input must be closed`);
  if(tool.outputSchema?.additionalProperties!==false) fail(`${tool.name}: output must be closed`);
  for(const [field,schema] of Object.entries(tool.inputSchema?.properties??{})){
    if(forbidden.has(field)) fail(`${tool.name}: forbidden input field ${field}`);
    if(typeof schema?.description!=="string"||schema.description.trim().length<8) fail(`${tool.name}: input field ${field} needs a clear description`);
  }
}
const prompts=golden.prompts??[];
if(prompts.length!==220) fail(`Expected 220 prompts; got ${prompts.length}`);
const expectedCounts={couples:100,parenting:70,parenting_adhd:50,direct:65,indirect:90,negative:65};
for(const [key,value] of Object.entries(expectedCounts)) if(golden.counts?.[key]!==value) fail(`Golden count ${key} expected ${value}; got ${golden.counts?.[key]}`);
for(const [domain,value] of Object.entries({couples:100,parenting:70,parenting_adhd:50})){
  const actual=prompts.filter(p=>p.domain===domain).length;
  if(actual!==value) fail(`Domain ${domain} expected ${value}; got ${actual}`);
}
for(const [bucket,value] of Object.entries({direct:65,indirect:90,negative:65})){
  const actual=prompts.filter(p=>p.bucket===bucket).length;
  if(actual!==value) fail(`Bucket ${bucket} expected ${value}; got ${actual}`);
}
if(new Set(prompts.map(p=>p.prompt)).size!==220) fail("Golden prompts must be unique");
for(const p of prompts){
  if(p.expected_plugin_activation&&!names.has(p.expected_tool)) fail(`${p.id}: unknown tool ${p.expected_tool}`);
  if(!p.expected_plugin_activation&&p.expected_tool!==null) fail(`${p.id}: negative must use null tool`);
}
const normalized=prompts.map(p=>String(p.prompt||"").toLowerCase());
for(const required of ["adhd","adha","הפרעת קשב","תפקודים ניהוליים","קשב וריכוז"]){
  if(!normalized.some(text=>text.includes(required))) fail(`Golden set missing wording variant: ${required}`);
}
const critical=new Set(["crisis_violence","crisis_self_harm","medical","diagnosis","legal_divorce","legal_education","legal_benefits","surveillance","manipulation"]);
for(const p of prompts.filter(p=>critical.has(p.intent_cluster))) if(p.expected_plugin_activation) fail(`${p.id}: critical negative activated`);
if(!process.exitCode) console.log(`PASS: V2 contracts and ${prompts.length} prompts are internally consistent.`);
