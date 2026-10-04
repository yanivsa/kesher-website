const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const PLUGIN_ROOT = path.join(ROOT, 'plugin');
const LEGACY_ROOT = path.join(ROOT, 'chatgpt-plugin');
const errors = [];
const fail = (message) => errors.push(message);
const read = (file) => fs.readFileSync(file, 'utf8');
const readJson = (file) => JSON.parse(read(file));

if (fs.existsSync(LEGACY_ROOT)) fail('Legacy chatgpt-plugin/ package must be removed; plugin/ is the only canonical package.');

const manifestPath = path.join(PLUGIN_ROOT, 'plugin.json');
const mcpPath = path.join(PLUGIN_ROOT, 'mcp.json');
const contractPath = path.join(PLUGIN_ROOT, 'contracts', 'mcp-tools.v2.json');
for (const file of [manifestPath, mcpPath, contractPath]) {
  if (!fs.existsSync(file)) fail(`Missing canonical V2 file: ${path.relative(ROOT, file)}`);
}

let manifest, mcp, contracts;
try { manifest = readJson(manifestPath); } catch (error) { fail(`Invalid plugin.json: ${error.message}`); }
try { mcp = readJson(mcpPath); } catch (error) { fail(`Invalid mcp.json: ${error.message}`); }
try { contracts = readJson(contractPath); } catch (error) { fail(`Invalid V2 contract: ${error.message}`); }

if (manifest) {
  if (manifest.$schema !== 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json') fail('Unexpected Agent Plugins schema URL');
  if (manifest.name !== 'kesher-hebrew-relationship-parenting-tools') fail('Unexpected V2 plugin name');
  if (manifest.version !== '0.2.0') fail('Expected V2 plugin version 0.2.0');
  const ui = manifest.extensions?.['com.openai']?.interface;
  if (!ui) fail('Missing extensions.com.openai.interface');
  if (ui) {
    if (!/זוגיות/.test(ui.displayName || '') || !/הורים|הורות/.test(ui.displayName || '')) fail('Display name must cover couples and parenting');
    if (!/ADHD|קשב/.test(ui.longDescription || '')) fail('Long description must cover attention/ADHD parenting scope');
    for (const field of ['websiteURL', 'supportURL', 'privacyPolicyURL', 'termsOfServiceURL']) {
      try {
        const url = new URL(ui[field]);
        if (url.protocol !== 'https:') fail(`${field} must use HTTPS`);
      } catch { fail(`${field} must be a valid URL`); }
    }
    for (const field of ['logo', 'composerIcon']) {
      const rel = ui[field];
      if (typeof rel !== 'string' || !rel.startsWith('./')) fail(`${field} must use a package-relative path`);
      else if (!fs.existsSync(path.resolve(PLUGIN_ROOT, rel))) fail(`${field} asset missing`);
    }
  }
}

if (mcp) {
  const servers = mcp.mcpServers || {};
  if (Object.keys(servers).length !== 1 || !servers.kesher) fail('Exactly one kesher MCP server is required');
  if (servers.kesher?.type !== 'streamable-http') fail('Kesher MCP must use streamable-http');
  if (servers.kesher?.url !== 'https://kesher-mcp-v2-staging.yanivsa.workers.dev/mcp') fail('Unexpected V2 staging MCP URL');
}

if (contracts) {
  const expected = new Set(['get_conflict_pattern','get_conversation_plan','get_parenting_response_plan','get_adhd_parenting_plan','find_kesher_resource']);
  const tools = contracts.tools || [];
  if (tools.length !== 5 || tools.some((tool) => !expected.has(tool.name))) fail('V2 contract must expose exactly the five approved tools');
  for (const tool of tools) {
    if (tool.annotations?.readOnlyHint !== true || tool.annotations?.destructiveHint !== false) fail(`${tool.name}: invalid read-only annotations`);
    if (tool.inputSchema?.additionalProperties !== false) fail(`${tool.name}: input schema must reject extra fields`);
  }
}

const skillsRoot = path.join(PLUGIN_ROOT, 'skills');
const skillDirs = fs.existsSync(skillsRoot)
  ? fs.readdirSync(skillsRoot, { withFileTypes: true }).filter((entry) => entry.isDirectory()).map((entry) => entry.name)
  : [];
const expectedSkills = new Set(['relationship-conflict','parenting-guidance','parenting-attention']);
if (skillDirs.length !== 3 || skillDirs.some((name) => !expectedSkills.has(name))) fail('Canonical V2 package must contain exactly the three approved skills');
for (const name of expectedSkills) {
  const skillPath = path.join(skillsRoot, name, 'SKILL.md');
  const agentPath = path.join(skillsRoot, name, 'agents', 'openai.yaml');
  if (!fs.existsSync(skillPath)) fail(`Missing ${name}/SKILL.md`);
  if (!fs.existsSync(agentPath)) fail(`Missing ${name}/agents/openai.yaml`);
  if (fs.existsSync(agentPath)) {
    const agent = read(agentPath);
    if (!/allow_implicit_invocation:\s*true/.test(agent)) fail(`${name}: implicit invocation must be enabled`);
    if (!/value:\s*"kesher"/.test(agent)) fail(`${name}: MCP dependency must be kesher`);
  }
}

const privacy = read(path.join(ROOT, 'src/pages/Legal/PrivacyPolicy.tsx'));
if (!privacy.includes('כלי Kesher ב-ChatGPT וב-MCP') || !privacy.includes('Cloudflare Workers')) {
  fail('Privacy policy must accurately describe the V2 MCP service');
}
const terms = read(path.join(ROOT, 'src/pages/Legal/TermsOfUse.tsx'));
if (!terms.includes('שימוש בפלאגין ChatGPT') || !terms.includes('אינו יוצר יחסי')) {
  fail('Terms must cover ChatGPT plugin use and professional boundaries');
}

if (errors.length) {
  console.error('ChatGPT plugin validation failed:');
  errors.forEach((error) => console.error(`- ${error}`));
  process.exit(1);
}
console.log('Kesher V2 ChatGPT plugin validation passed.');
