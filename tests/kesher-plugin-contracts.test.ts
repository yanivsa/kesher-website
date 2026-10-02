import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

type JsonSchema = {
  type?: string;
  additionalProperties?: boolean;
  required?: string[];
  properties?: Record<string, unknown>;
};

type ToolContract = {
  name: string;
  title: string;
  description: string;
  annotations: {
    readOnlyHint: boolean;
    destructiveHint: boolean;
    openWorldHint: boolean;
  };
  inputSchema: JsonSchema;
  outputSchema: JsonSchema;
};

const here = dirname(fileURLToPath(import.meta.url));
const toolsPath = resolve(here, '../plugin/contracts/tools.json');
const safetyPath = resolve(here, '../plugin/contracts/safety-boundaries.json');
const promptsPath = resolve(here, '../plugin/evals/golden-prompts.json');

const toolsContract = JSON.parse(readFileSync(toolsPath, 'utf8')) as {
  tools: ToolContract[];
};
const safety = JSON.parse(readFileSync(safetyPath, 'utf8')) as {
  excluded_intents: Array<{ category: string; behavior: string }>;
  data_minimization: { forbidden_input_fields: string[] };
};
const golden = JSON.parse(readFileSync(promptsPath, 'utf8')) as {
  prompts: Array<{
    bucket: 'direct' | 'indirect' | 'negative';
    expected_plugin_activation: boolean;
    expected_tool: string | null;
    intent_cluster: string;
  }>;
};

describe('Kesher plugin V1 contracts', () => {
  it('exposes exactly the two approved read-only V1 tools', () => {
    expect(toolsContract.tools.map((tool) => tool.name)).toEqual([
      'get_conflict_pattern',
      'get_conversation_plan',
    ]);

    for (const tool of toolsContract.tools) {
      expect(tool.annotations).toEqual({
        readOnlyHint: true,
        destructiveHint: false,
        openWorldHint: false,
      });
    }
  });

  it('uses precise metadata with explicit negative boundaries', () => {
    for (const tool of toolsContract.tools) {
      expect(tool.title.length).toBeGreaterThan(10);
      expect(tool.description.startsWith('Use this when')).toBe(true);
      expect(tool.description).toContain('Do not use for');
      for (const boundary of [
        'violence',
        'self-harm',
        'legal',
        'medical',
        'diagnosis',
        'surveillance',
        'manipulation',
      ]) {
        expect(tool.description).toContain(boundary);
      }
    }
  });

  it('keeps both input and output schemas closed and structured', () => {
    for (const tool of toolsContract.tools) {
      expect(tool.inputSchema.type).toBe('object');
      expect(tool.inputSchema.additionalProperties).toBe(false);
      expect(tool.outputSchema.type).toBe('object');
      expect(tool.outputSchema.additionalProperties).toBe(false);
      expect(tool.inputSchema.required?.length).toBeGreaterThan(0);
      expect(tool.outputSchema.required?.length).toBeGreaterThan(0);
    }
  });

  it('does not allow raw narratives or direct identifiers in tool inputs', () => {
    const forbidden = new Set(safety.data_minimization.forbidden_input_fields);

    for (const tool of toolsContract.tools) {
      const propertyNames = Object.keys(tool.inputSchema.properties ?? {});
      for (const propertyName of propertyNames) {
        expect(forbidden.has(propertyName)).toBe(false);
      }
    }
  });

  it('keeps the golden prompt routing synchronized with the declared tool names', () => {
    const toolNames = new Set(toolsContract.tools.map((tool) => tool.name));
    const positive = golden.prompts.filter((prompt) => prompt.bucket !== 'negative');
    const negative = golden.prompts.filter((prompt) => prompt.bucket === 'negative');

    expect(positive.length).toBe(70);
    expect(negative.length).toBe(30);

    for (const prompt of positive) {
      expect(prompt.expected_plugin_activation).toBe(true);
      expect(prompt.expected_tool).not.toBeNull();
      expect(toolNames.has(prompt.expected_tool as string)).toBe(true);
    }

    for (const prompt of negative) {
      expect(prompt.expected_plugin_activation).toBe(false);
      expect(prompt.expected_tool).toBeNull();
    }
  });

  it('explicitly excludes all high-risk negative clusters from V1', () => {
    const excluded = new Set(safety.excluded_intents.map((item) => item.category));
    const requiredExclusions = [
      'crisis_violence',
      'crisis_self_harm',
      'legal_divorce',
      'medical',
      'sexual_health',
      'diagnosis',
      'surveillance',
      'infidelity_surveillance',
      'manipulation',
    ];

    for (const category of requiredExclusions) {
      expect(excluded.has(category)).toBe(true);
    }

    const highRiskGolden = golden.prompts.filter((prompt) =>
      requiredExclusions.includes(prompt.intent_cluster),
    );

    expect(highRiskGolden.length).toBeGreaterThan(0);
    for (const prompt of highRiskGolden) {
      expect(prompt.bucket).toBe('negative');
      expect(prompt.expected_plugin_activation).toBe(false);
    }
  });
});
