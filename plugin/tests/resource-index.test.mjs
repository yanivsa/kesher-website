import assert from "node:assert/strict";
import data from "../data/kesher-resources.json" with { type: "json" };
import posts from "../../src/data/posts.json" with { type: "json" };

assert.ok(data.count>=90,`Expected broad Kesher resource coverage; got ${data.count}`);
assert.equal(data.count,data.resources.length);
const domains=new Set(data.resources.map(r=>r.domain));
for(const d of ["couples","parenting","parenting_adhd"])assert.ok(domains.has(d),`Missing domain ${d}`);
assert.ok(data.resources.some(r=>r.domain==="parenting_adhd"&&r.topics.includes("adhd_morning")),"Missing ADHD morning resource");
assert.ok(data.resources.some(r=>r.domain==="parenting"&&r.topics.includes("screens")),"Missing parenting screens resource");

const sourcePosts=Array.isArray(posts)?posts:(posts.posts??[]);
const sourceIds=new Set(sourcePosts.map(p=>p.id));
for(const r of data.resources){
  assert.ok(sourceIds.has(r.slug),`Resource slug must use canonical post id: ${r.slug}`);
  assert.equal(r.url,`https://kesher.saharoni.com/blog/${r.slug}`);
}
console.log(`PASS: Kesher resource index covers ${data.count} canonical resources across all V2 domains.`);
