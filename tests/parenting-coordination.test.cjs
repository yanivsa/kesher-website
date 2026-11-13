const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { loadPosts } = require('../scripts/load-posts.cjs');
const { isPublishable, STATIC_ROUTES } = require('../scripts/content-policy.cjs');

const root = path.resolve(__dirname, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');
const service = '/services/parenting-coordination';
const category = '/blog/category/parenting-coordination';
const postIds = ['what-is-parenting-coordination', 'parenting-coordination-vs-mediation', 'divorced-parents-communication', 'parenting-time-holidays-after-divorce', 'can-one-parent-start-parenting-coordination'];

assert(STATIC_ROUTES.includes(service), 'service must be registered for prerender and sitemap');
assert(STATIC_ROUTES.includes(category), 'category must be registered for prerender and sitemap');
const app = read('src/App.tsx');
assert(app.includes('<Route path="' + service + '"'), 'service route must be mounted');
assert(app.includes('<Route path="' + category + '"'), 'category route must be mounted');
assert(app.indexOf('<Route path="' + category + '"') < app.indexOf('<Route path="/blog/:id"'), 'category route must precede article param route');
assert(app.includes('parentingCoordinationCategory.preload'), 'category must be preloaded');
assert(app.includes('parentingCoordination.preload'), 'service must be preloaded');

const posts = loadPosts().filter((p) => postIds.includes(p.id));
assert.equal(posts.length, 5, 'editorial hub must have five distinct published articles');
for (const post of posts) {
  assert.equal(post.category, 'תיאום הורי', post.id + ' category mismatch');
  assert(isPublishable(post), post.id + ' must satisfy editorial length and sections');
  const visibleText = post.content.replace(/<[^>]*>/g, ' ').replace(/&[^;]+;/g, ' ').trim();
  const words = visibleText.split(/\s+/).filter(Boolean);
  assert(words.length >= 850, post.id + ' should provide an in-depth practical guide (850+ words)');
  assert((post.content.match(/<h3>/g) || []).length >= 7, post.id + ' should have scannable topical sections');
  assert(post.directAnswer && post.directAnswer.length >= 75 && post.directAnswer.length <= 350, post.id + ' needs concise GEO answer');
  assert.equal(post.updatedAt, '2026-11-13', post.id + ' updated editorial date must match substantive revision');
  assert(!/\b(100%|מובטח|הצלחה מובטחת|ממונה מטעם בית משפט|מתאמת הורית מוסמכת)\b/.test(visibleText), post.id + ' must not imply guaranteed outcomes or unverified credentials');
  assert(post.content.includes('בטיחות') || post.content.includes('אלימות'), post.id + ' must discuss safety suitability');
  assert(post.content.includes('href="/services/parenting-coordination"') || post.content.includes('href="/blog/'), post.id + ' needs internal topic links');

  assert(post.content.includes('href="/services/parenting-coordination"') || post.content.includes('href="/blog/'), post.id + ' lacks internal linking');
  assert(post.image && post.image.startsWith('/images/'), post.id + ' needs local artwork');
  assert(fs.existsSync(path.join(root, 'public', post.image.slice(1))), post.id + ' image missing');
  assert(post.imageAlt && post.imageAlt.length >= 20, post.id + ' requires specific alt text');
  assert(Array.isArray(post.evidence) && post.evidence.length >= 1, post.id + ' needs professional source');
  assert(!/<strong>מקורות (?:להעמקה|מקצועיים):<\/strong>/.test(post.content), post.id + ' should not duplicate the standard evidence component');
  for (const evidence of post.evidence) {
    assert(/^https:\/\//.test(evidence.url), post.id + ' must cite absolute HTTPS sources');
  }
  assert(!/[A-Za-z]/.test(post.content.replace(/<[^>]*>/g, ' ')), post.id + ' visible copy must remain in Hebrew');
  assert(post.relatedPostIds?.length >= 2, post.id + ' needs interlinked cluster');
}
const serviceContent = read('src/pages/Services/ParentingCoordination/ParentingCoordinationPage.tsx');
assert(serviceContent.includes('data-analytics-service-type="parenting_coordination"'));
assert(serviceContent.includes('service_inquiry_start'));
assert(serviceContent.includes('בירור ראשוני והתאמה'));
assert(!/מתאמת הורית מוסמכת|ניסיון של \d+ שנים בתיאום הורי|ממונה מטעם בית משפט/.test(serviceContent), 'unverified credentials or appointment claim');
assert(read('src/components/Layout/Header.tsx').includes('to="' + service + '"'));
assert(read('src/components/Layout/Footer.tsx').includes('to="' + service + '"'));
assert(read('src/pages/Blog/BlogList.tsx').includes('to="' + category + '"'));

console.log('Parenting coordination service, editorial catalog, route and policy checks passed.');
