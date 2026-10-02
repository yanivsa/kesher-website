import fs from "node:fs";
import path from "node:path";

const root = path.resolve(new URL("..", import.meta.url).pathname);
const repoRoot = path.resolve(root, "..");

const readJson = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
const fail = (message) => {
  console.error("FAIL:", message);
  process.exitCode = 1;
};

const manifest = readJson(path.join(root, "plugin.json"));
const mcp = readJson(path.join(root, "mcp.json"));
const marketplace = readJson(path.join(repoRoot, ".agents/plugins/marketplace.json"));

if (manifest.$schema !== "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json") {
  fail("plugin.json must use the Agent Plugins 1.0 schema");
}
if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(manifest.name ?? "")) {
  fail("plugin name must be stable kebab-case");
}
if (manifest.version !== "0.1.0") fail("unexpected plugin version");
if (!manifest.description) fail("plugin description is required");

const iface = manifest.extensions?.["com.openai"]?.interface;
if (!iface) fail("OpenAI interface metadata is required for this package");
if ((iface?.displayName ?? "").length > 30) fail("displayName exceeds 30 characters");
if ((iface?.shortDescription ?? "").length > 30) fail("shortDescription exceeds 30 characters");
if ((iface?.longDescription ?? "").length > 4000) fail("longDescription exceeds 4000 characters");
if (!["Productivity","Creativity","Developer Tools","Business & Operations","Data & Analytics","Communication","Education & Research","Security","Finance","Healthcare","Travel","Entertainment","Other"].includes(iface?.category)) {
  fail("unsupported OpenAI category");
}
if (!Array.isArray(iface?.capabilities) || !iface.capabilities.includes("Read")) {
  fail("interface capabilities must declare Read");
}
if (iface?.privacyPolicyURL) {
  fail("Do not publish a placeholder privacyPolicyURL; add it only after a real policy is live");
}

if (mcp.$schema !== "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json") {
  fail("mcp.json must use the Agent Plugins MCP 1.0 schema");
}
const servers = mcp.mcpServers ?? {};
if (Object.keys(servers).length !== 1 || !servers.kesher) {
  fail("V1 package must declare exactly one MCP server named kesher");
}
if (servers.kesher?.type !== "streamable-http") fail("Kesher MCP transport must be streamable-http");
if (servers.kesher?.url !== "https://kesher-mcp-staging.yanivsa.workers.dev/mcp") {
  fail("Local package must point at the known staging MCP endpoint");
}

if (marketplace.name !== "kesher-local") fail("unexpected marketplace name");
const entry = (marketplace.plugins ?? []).find((p) => p.name === manifest.name);
if (!entry) fail("marketplace does not expose the Kesher plugin");
if (entry?.source?.source !== "local" || entry?.source?.path !== "./plugin") {
  fail("marketplace source must resolve to ./plugin from the repo root");
}
if (entry?.policy?.installation !== "AVAILABLE") fail("local plugin must remain opt-in");
if (!["ON_INSTALL","ON_USE"].includes(entry?.policy?.authentication)) {
  fail("marketplace authentication policy must use a supported value");
}

if (!process.exitCode) {
  console.log("PASS: Kesher portable plugin package and local marketplace are internally consistent.");
}
