const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const PLUGIN_ROOT = path.join(ROOT, 'chatgpt-plugin');
const MANIFEST_PATH = path.join(PLUGIN_ROOT, 'plugin.json');
const errors = [];

const fail = (message) => errors.push(message);
const read = (file) => fs.readFileSync(file, 'utf8');

if (!fs.existsSync(MANIFEST_PATH)) {
  fail('Missing chatgpt-plugin/plugin.json');
} else {
  let manifest;
  try {
    manifest = JSON.parse(read(MANIFEST_PATH));
  } catch (error) {
    fail(`Invalid plugin.json: ${error.message}`);
  }

  if (manifest) {
    if (manifest.$schema !== 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json') {
      fail('Unexpected Agent Plugins schema URL');
    }
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(manifest.name || '')) {
      fail('Plugin name must match public submission naming rules');
    }
    if (!/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/.test(manifest.version || '')) {
      fail('Plugin version must be semantic versioning');
    }
    if (manifest.skills !== './skills/') fail('Plugin must declare ./skills/');
    if (manifest.mcpServers || manifest.apps) fail('Skills-only package must not declare MCP/apps');

    const openai = manifest.extensions?.['com.openai'];
    const ui = openai?.interface;
    if (!ui) fail('Missing extensions.com.openai.interface');

    if (ui) {
      const max = (label, value, limit) => {
        if (typeof value !== 'string' || !value.trim()) fail(`${label} is required`);
        else if (value.length > limit) fail(`${label} exceeds ${limit} characters`);
        if (typeof value === 'string' && /[\r\n]/.test(value) && label !== 'longDescription') {
          fail(`${label} must be one line`);
        }
      };

      max('displayName', ui.displayName, 30);
      max('shortDescription', ui.shortDescription, 30);
      max('longDescription', ui.longDescription, 4000);
      max('developerName', ui.developerName, 80);

      const categories = new Set([
        'Productivity', 'Creativity', 'Developer Tools', 'Business & Operations',
        'Data & Analytics', 'Communication', 'Education & Research', 'Security',
        'Finance', 'Healthcare', 'Travel', 'Entertainment', 'Other',
      ]);
      if (!categories.has(ui.category)) fail(`Unsupported category: ${ui.category}`);

      if (!Array.isArray(ui.capabilities) || ui.capabilities.length > 20) {
        fail('capabilities must be an array with at most 20 entries');
      } else {
        ui.capabilities.forEach((item, index) => {
          if (typeof item !== 'string' || !item.trim() || item.length > 120 || /[\r\n]/.test(item)) {
            fail(`Invalid capability at index ${index}`);
          }
        });
      }

      if (!Array.isArray(ui.defaultPrompt) || ui.defaultPrompt.length < 1 || ui.defaultPrompt.length > 3) {
        fail('defaultPrompt must contain 1-3 prompts');
      } else {
        const normalized = new Set();
        ui.defaultPrompt.forEach((prompt, index) => {
          if (typeof prompt !== 'string' || !prompt.trim() || prompt.length > 128 || /[\r\n]/.test(prompt)) {
            fail(`Invalid starter prompt at index ${index}`);
          }
          if (prompt.includes('@')) fail(`Starter prompt ${index} must not contain @mentions`);
          const key = prompt.normalize('NFKC').replace(/\s+/g, ' ').trim();
          if (normalized.has(key)) fail(`Duplicate starter prompt at index ${index}`);
          normalized.add(key);
        });
      }

      for (const field of ['websiteURL', 'supportURL', 'privacyPolicyURL', 'termsOfServiceURL']) {
        const value = ui[field];
        try {
          const url = new URL(value);
          if (url.protocol !== 'https:' || !url.hostname) fail(`${field} must be an HTTPS URL`);
          if (value.length > 1024) fail(`${field} exceeds 1024 characters`);
        } catch {
          fail(`${field} must be a valid URL`);
        }
      }

      for (const field of ['logo', 'composerIcon']) {
        const rel = ui[field];
        if (typeof rel !== 'string' || !rel.startsWith('./')) {
          fail(`${field} must use a ./-prefixed package path`);
          continue;
        }
        const abs = path.resolve(PLUGIN_ROOT, rel);
        if (!abs.startsWith(PLUGIN_ROOT + path.sep) || !fs.existsSync(abs)) {
          fail(`${field} does not resolve to an included asset`);
          continue;
        }
        if (path.extname(abs).toLowerCase() === '.svg') {
          const svg = read(abs);
          const match = svg.match(/viewBox=["']\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*["']/i);
          if (!match) fail(`${field} SVG needs a numeric viewBox`);
          else {
            const width = Number(match[3]);
            const height = Number(match[4]);
            if (width !== height || width < 48) fail(`${field} SVG must be square and at least 48x48`);
          }
        }
      }
    }

    if (!Array.isArray(openai?.publication?.countries) || !openai.publication.countries.includes('IL')) {
      fail('Publication countries must include IL');
    }
  }
}

for (const forbidden of ['mcp.json', '.mcp.json', '.app.json']) {
  if (fs.existsSync(path.join(PLUGIN_ROOT, forbidden))) fail(`Skills-only package must not include ${forbidden}`);
}

const skillsRoot = path.join(PLUGIN_ROOT, 'skills');
if (!fs.existsSync(skillsRoot)) {
  fail('Missing skills directory');
} else {
  const dirs = fs.readdirSync(skillsRoot, { withFileTypes: true }).filter((entry) => entry.isDirectory());
  if (dirs.length < 1) fail('Skills-only package must contain at least one skill');

  const pluginName = fs.existsSync(MANIFEST_PATH) ? JSON.parse(read(MANIFEST_PATH)).name : '';
  for (const dir of dirs) {
    if (dir.name.startsWith('.')) fail(`Hidden skill directory is not allowed: ${dir.name}`);
    const skillPath = path.join(skillsRoot, dir.name, 'SKILL.md');
    const agentPath = path.join(skillsRoot, dir.name, 'agents', 'openai.yaml');
    if (!fs.existsSync(skillPath)) {
      fail(`Missing SKILL.md for ${dir.name}`);
      continue;
    }
    const skill = read(skillPath);
    const fm = skill.match(/^---\n([\s\S]*?)\n---\n/);
    if (!fm) {
      fail(`Missing YAML front matter in ${dir.name}/SKILL.md`);
      continue;
    }
    const name = fm[1].match(/^name:\s*(.+)$/m)?.[1]?.trim();
    const description = fm[1].match(/^description:\s*(.+)$/m)?.[1]?.trim();
    if (!name || !description) fail(`Skill ${dir.name} needs name and description`);
    if (description && description.length > 1024) fail(`Skill ${dir.name} description exceeds 1024 characters`);
    if (name && `${pluginName}:${name}`.length > 64) fail(`Combined plugin:skill identity exceeds 64 characters for ${dir.name}`);
    if (!skill.slice(fm[0].length).trim()) fail(`Skill ${dir.name} body is empty`);

    if (!fs.existsSync(agentPath)) {
      fail(`Missing agents/openai.yaml for ${dir.name}`);
    } else {
      const agent = read(agentPath);
      if (!/products:\s*\n\s*- CHAT/.test(agent)) fail(`${dir.name} must target CHAT`);
      if (!/allow_implicit_invocation:\s*true/.test(agent)) fail(`${dir.name} must allow implicit invocation`);
    }
  }
}

const privacy = read(path.join(ROOT, 'src/pages/Legal/PrivacyPolicy.tsx'));
const terms = read(path.join(ROOT, 'src/pages/Legal/TermsOfUse.tsx'));
if (!privacy.includes('פלאגין ChatGPT') || !privacy.includes('אינו מפעיל שרת MCP')) {
  fail('Privacy policy must explicitly describe the skills-only ChatGPT plugin');
}
if (!terms.includes('שימוש בפלאגין ChatGPT') || !terms.includes('אינו יוצר יחסי')) {
  fail('Terms must explicitly cover ChatGPT plugin use and professional boundaries');
}

if (errors.length) {
  console.error('ChatGPT plugin validation failed:');
  errors.forEach((error) => console.error(`- ${error}`));
  process.exit(1);
}

console.log('ChatGPT plugin package validation passed.');
