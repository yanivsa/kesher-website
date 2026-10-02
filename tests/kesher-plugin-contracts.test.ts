import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

type ToolContract = {
  name: string;
  annotations: {
    readOnlyHint: boolean;
    destructiveHint: boolean;
    openWorldHint: boolean;
    idempotentHint: boolean;
  };
  inputSchema: { additionalProperties: boolean; properties?: Record<string, unknown> };
  outputSchema: { additionalProperties: boolean };
};
type GoldenPrompt = {
  prompt: string;
  expected_plugin_activation: boolean;
  expected_tool: string | null;
};

const here=dirname(fileURLToPath(import.meta.url));
const contract=JSON.parse(readFileSync(resolve(here,'../plugin/contracts/mcp-tools.v2.json'),'utf8')) as { tools: ToolContract[] };
const safety=JSON.parse(readFileSync(resolve(here,'../plugin/contracts/safety-boundaries.json'),'utf8')) as { data_minimization: { forbidden_input_fields: string[] } };
const golden=JSON.parse(readFileSync(resolve(here,'../plugin/evals/golden-prompts.json'),'utf8')) as { prompts: GoldenPrompt[] };

describe('Kesher plugin V2 contracts',()=>{
  it('exposes exactly five read-only tools',()=>{
    expect(contract.tools.map((tool)=>tool.name)).toEqual([
      'get_conflict_pattern','get_conversation_plan','get_parenting_response_plan','get_adhd_parenting_plan','find_kesher_resource'
    ]);
    for(const tool of contract.tools) {
      expect(tool.annotations).toEqual({readOnlyHint:true,destructiveHint:false,openWorldHint:false,idempotentHint:true});
    }
  });

  it('uses closed schemas and excludes private fields',()=>{
    const forbidden=new Set(safety.data_minimization.forbidden_input_fields);
    for(const tool of contract.tools){
      expect(tool.inputSchema.additionalProperties).toBe(false);
      expect(tool.outputSchema.additionalProperties).toBe(false);
      for(const key of Object.keys(tool.inputSchema.properties??{})) expect(forbidden.has(key)).toBe(false);
    }
  });

  it('routes all 220 prompts only to declared tools',()=>{
    const names=new Set(contract.tools.map((tool)=>tool.name));
    expect(golden.prompts).toHaveLength(220);
    expect(new Set(golden.prompts.map((prompt)=>prompt.prompt)).size).toBe(220);
    for(const prompt of golden.prompts){
      if(prompt.expected_plugin_activation) expect(names.has(prompt.expected_tool ?? '')).toBe(true);
      else expect(prompt.expected_tool).toBeNull();
    }
  });
});
