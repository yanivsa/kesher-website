import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
const here=dirname(fileURLToPath(import.meta.url));
const contract=JSON.parse(readFileSync(resolve(here,'../plugin/contracts/mcp-tools.v2.json'),'utf8'));
const safety=JSON.parse(readFileSync(resolve(here,'../plugin/contracts/safety-boundaries.json'),'utf8'));
const golden=JSON.parse(readFileSync(resolve(here,'../plugin/evals/golden-prompts.json'),'utf8'));
describe('Kesher plugin V2 contracts',()=>{
  it('exposes exactly five read-only tools',()=>{
    expect(contract.tools.map((t:any)=>t.name)).toEqual([
      'get_conflict_pattern','get_conversation_plan','get_parenting_response_plan','get_adhd_parenting_plan','find_kesher_resource'
    ]);
    for(const t of contract.tools) expect(t.annotations).toEqual({readOnlyHint:true,destructiveHint:false,openWorldHint:false,idempotentHint:true});
  });
  it('uses closed schemas and excludes private fields',()=>{
    const forbidden=new Set(safety.data_minimization.forbidden_input_fields);
    for(const t of contract.tools){
      expect(t.inputSchema.additionalProperties).toBe(false);
      expect(t.outputSchema.additionalProperties).toBe(false);
      for(const k of Object.keys(t.inputSchema.properties??{})) expect(forbidden.has(k)).toBe(false);
    }
  });
  it('routes all 220 prompts only to declared tools',()=>{
    const names=new Set(contract.tools.map((t:any)=>t.name));
    expect(golden.prompts).toHaveLength(220);
    expect(new Set(golden.prompts.map((p:any)=>p.prompt)).size).toBe(220);
    for(const p of golden.prompts){
      if(p.expected_plugin_activation) expect(names.has(p.expected_tool)).toBe(true);
      else expect(p.expected_tool).toBeNull();
    }
  });
});
