import fs from "node:fs";import path from "node:path";
const root=path.resolve(new URL("..",import.meta.url).pathname),repoRoot=path.resolve(root,"..");
const readJson=p=>JSON.parse(fs.readFileSync(p,"utf8"));const fail=m=>{console.error("FAIL:",m);process.exitCode=1;};
const manifest=readJson(path.join(root,"plugin.json")),mcp=readJson(path.join(root,"mcp.json")),marketplace=readJson(path.join(repoRoot,".agents/plugins/marketplace.json"));
if(fs.existsSync(path.join(repoRoot,"chatgpt-plugin")))fail("legacy chatgpt-plugin package must not coexist with canonical V2 plugin");
if(manifest.$schema!=="https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")fail("plugin schema");
if(manifest.version!=="0.2.0")fail("expected V2 manifest version 0.2.0");
if(manifest.name!=="kesher-hebrew-relationship-parenting-tools")fail("unexpected V2 plugin name");
const iface=manifest.extensions?.["com.openai"]?.interface;
if(!iface)fail("OpenAI interface required");
if((iface.displayName??"").length>30)fail("displayName too long");
if((iface.shortDescription??"").length>30)fail("shortDescription too long");
if(iface.privacyPolicyURL!=="https://kesher.saharoni.com/privacy")fail("privacy URL");
if(iface.supportURL!=="https://kesher.saharoni.com/contact")fail("support URL");
if(iface.termsOfServiceURL!=="https://kesher.saharoni.com/terms")fail("terms URL");
for(const assetField of ["logo","composerIcon"]){
  const rel=iface[assetField];
  if(typeof rel!=="string"||!rel.startsWith("./assets/"))fail(`${assetField} path`);
  else if(!fs.existsSync(path.join(root,rel.slice(2))))fail(`${assetField} file missing`);
}
if(!/הורות/.test(iface.longDescription??"")||!/ADHD|קשב/.test(iface.longDescription??""))fail("V2 metadata must cover parenting and attention");
for(const keyword of ["זוגיות","הדרכת הורים","קשב","ADHD"]) if(!(manifest.keywords??[]).includes(keyword)) fail(`missing discovery keyword: ${keyword}`);
const servers=mcp.mcpServers??{};if(Object.keys(servers).length!==1||servers.kesher?.type!=="streamable-http")fail("MCP config");
if(servers.kesher?.url!=="https://kesher-mcp-v2-staging.yanivsa.workers.dev/mcp")fail("isolated V2 staging MCP URL");
const review=manifest.extensions?.["com.openai"]?.review;
if(review?.test_cases?.positive?.length!==5)fail("review requires exactly 5 positive test cases");
if(review?.test_cases?.negative?.length!==3)fail("review requires exactly 3 negative test cases");
for(const testCase of review?.test_cases?.positive??[]){
  if(!testCase.description||!testCase.prompt||!testCase.tools_triggered||!testCase.expected_behavior)fail("incomplete positive review case");
}
for(const testCase of review?.test_cases?.negative??[]){
  if(!testCase.description||!testCase.prompt)fail("incomplete negative review case");
}
if(review?.commerce!==false)fail("commerce must be false");
if(!(manifest.extensions?.["com.openai"]?.publication?.release_notes??"").trim())fail("release notes required");
const entry=(marketplace.plugins??[]).find(p=>p.name===manifest.name);if(!entry)fail("marketplace missing V2 plugin");
if(entry?.source?.path!=="./plugin"||entry?.policy?.installation!=="AVAILABLE")fail("marketplace policy");
if(!process.exitCode)console.log("PASS: Kesher V2 portable plugin package is internally consistent.");
