const fs = require('fs');
const path = require('path');
const { ROOT, STATIC_ROUTES, isPublishable, blogRoute, wordCount, headingCount, stripHtml } = require('./content-policy.cjs');

const posts = JSON.parse(fs.readFileSync(path.join(ROOT, 'src/data/posts.json'), 'utf8'));
const published = posts.filter(isPublishable);
const errors = [];
const ensureUnique = (label, values) => {
  const seen = new Set();
  for (const value of values) {
    if (seen.has(value)) errors.push(`Duplicate ${label}: ${value}`);
    seen.add(value);
  }
};

ensureUnique('post id', published.map((post) => post.id));
ensureUnique('post title', published.map((post) => post.title));
ensureUnique('post image', published.map((post) => post.image));

for (let i = 0; i < published.length; i++) {
  const post = published[i];
  if (!/^\d{4}-\d{2}-\d{2}$/.test(post.date)) errors.push(`Invalid date: ${post.id}`);
  if (!post.image.startsWith('/images/')) errors.push(`Non-local image: ${post.id}`);
  if (!fs.existsSync(path.join(ROOT, 'public', post.image.replace(/^\//, '')))) errors.push(`Missing image: ${post.id}`);
  if (/<script|onerror=|onclick=|javascript:/i.test(post.content)) errors.push(`Unsafe HTML: ${post.id}`);
  if (wordCount(post.content) < 500 || headingCount(post.content) < 5) errors.push(`Thin content: ${post.id}`);
  if (/מוסמכת|הדרך היחידה|טראומות לא נשכחות/.test(post.content)) errors.push(`Unsupported absolute claim: ${post.id}`);

  if (post.date > '2026-07-15') {
    if (/[a-zA-Z]/.test(post.title) || /[a-zA-Z]/.test(post.excerpt) || /[a-zA-Z]/.test(stripHtml(post.content))) {
      errors.push(`Latin characters found in visible prose: ${post.id}`);
    }

    const STOP_WORDS = new Set(['couples', 'parenting', 'relationship', 'children', 'child', 'with', 'about', 'how', 'why', 'what', 'when', 'your', 'their']);
    const getWords = (id) => new Set(id.split('-').filter(w => w.length > 3 && !STOP_WORDS.has(w.toLowerCase())));
    const currentWords = getWords(post.id);

    for (let j = i + 1; j < Math.min(i + 31, published.length); j++) {
      const olderPost = published[j];
      const olderWords = getWords(olderPost.id);
      const intersection = [...currentWords].filter(x => olderWords.has(x));

      if (intersection.length >= 2) {
        errors.push(`Topic too similar: '${post.id}' shares specific theme keywords (${intersection.join(', ')}) with recent post '${olderPost.id}'. Please write about a substantially fresh topic.`);
        break;
      }
    }
  }
}

const sitemap = fs.readFileSync(path.join(ROOT, 'public/sitemap.xml'), 'utf8');
for (const route of [...STATIC_ROUTES, ...published.map(blogRoute)]) {
  const url = `https://kesher.saharoni.com${route === '/' ? '/' : route}`;
  if (!sitemap.includes(`<loc>${url}</loc>`)) errors.push(`Missing sitemap URL: ${url}`);
}
for (const post of posts.filter((post) => !isPublishable(post))) {
  if (sitemap.includes(`/blog/${post.id}</loc>`)) errors.push(`Thin post remains indexed: ${post.id}`);
}

const unsupportedClaims = [
  /(מטפלת|פסיכולוגית|פסיכותרפיסטית|עובדת סוציאלית|מאמנת)\s+מוסמכת/,
  /מומחית/,
  /\bGottman\b/i,
  /\bEFT\b/,
  /licensed therapist/i,
  /הסיכויים להצלחה גבוהים יותר/,
  /יעילה יותר מטיפול ישיר/,
  /המנגנון הנוירולוגי של הילד/,
];
const claimFiles = [
  'src/constants/siteConfig.ts',
  'src/pages/Home/Home.tsx',
  'src/pages/About/AboutPage.tsx',
  'src/pages/Services/Couples/CouplesCounseling.tsx',
  'src/pages/Services/Parenting/ParentingGuidance.tsx',
  'src/pages/Services/Mediation/MediationPage.tsx',
  'src/pages/Services/Gifted/GiftedParentingPage.tsx',
  'src/pages/Services/Aliyah/AliyahFamiliesPage.tsx',
  'src/data/faqs.ts',
  'public/llms.txt',
];
for (const relative of claimFiles) {
  const content = fs.readFileSync(path.join(ROOT, relative), 'utf8');
  for (const pattern of unsupportedClaims) {
    if (pattern.test(content)) errors.push(`Unsupported claim in ${relative}: ${pattern}`);
  }
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(`Validated ${published.length} published posts; ${posts.length - published.length} thin legacy posts remain unindexed.`);
