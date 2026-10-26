const fs = require('fs');
const path = require('path');
const { loadPosts } = require('./load-posts.cjs');
const {
  extractBlogLinks,
  validateInternalLinkPlan,
  auditInternalLinkCoverage,
} = require('./internal-link-policy.cjs');

const planFiles = [
  'internal-link-plan.json',
  'internal-link-plan-priority2.json',
  'internal-link-plan-priority3.json',
];
const backfillFiles = [
  path.join(__dirname, '..', 'src', 'data', 'internalLinkBackfill.json'),
  path.join(__dirname, '..', 'src', 'data', 'internalLinkBackfillManual.json'),
];

const plan = planFiles.flatMap((fileName) => {
  const filePath = path.join(__dirname, fileName);
  return fs.existsSync(filePath) ? JSON.parse(fs.readFileSync(filePath, 'utf8')) : [];
});
const backfillRules = backfillFiles.flatMap((filePath) =>
  fs.existsSync(filePath) ? JSON.parse(fs.readFileSync(filePath, 'utf8')) : [],
);
const posts = loadPosts();
const errors = validateInternalLinkPlan(posts, plan);

if (errors.length) {
  console.error('Internal-link plan is invalid:');
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

const normalizeHeading = (html) => String(html || '')
  .replace(/<[^>]+>/g, ' ')
  .replace(/&quot;/gi, '"')
  .replace(/&#(?:39|x27);/gi, "'")
  .replace(/&amp;/gi, '&')
  .replace(/&nbsp;/gi, ' ')
  .replace(/\s+/g, ' ')
  .trim();

const hasPlacementHeading = (content, needle) => {
  const re = /<h3\b[^>]*>([\s\S]*?)<\/h3>/gi;
  let match;
  while ((match = re.exec(content))) {
    if (normalizeHeading(match[1]).includes(needle)) return true;
  }
  return false;
};

const effectivePosts = posts.map((post) => {
  const matchingRules = backfillRules.filter((candidate) => candidate.source === post.id);
  if (matchingRules.length === 0) return post;

  let content = post.content;
  for (const rule of matchingRules) {
    if (!hasPlacementHeading(content, rule.afterHeadingIncludes)) continue;

    const existing = new Set(extractBlogLinks(content));
    const overlayLinks = rule.items
      .filter((item) => typeof item.target === 'string' && !existing.has(`/blog/${item.target}`))
      .map((item) => `<a href="/blog/${item.target}">${item.anchor}</a>`)
      .join('');

    if (overlayLinks) content = `${content}${overlayLinks}`;
  }

  return content === post.content ? post : { ...post, content };
});

const audit = auditInternalLinkCoverage(effectivePosts, plan);
const clusters = new Map();
for (const entry of plan) {
  const row = clusters.get(entry.cluster) || { planned: 0, present: 0 };
  for (const target of entry.targets) {
    row.planned += 1;
    if (audit.rows.some((item) => item.source === entry.source && item.target === target && item.present)) {
      row.present += 1;
    }
  }
  clusters.set(entry.cluster, row);
}

console.log(`Internal-link plan valid: ${plan.length} source-plan entries, ${audit.planned} planned article-to-article links.`);
console.log(`Coverage now: ${audit.present}/${audit.planned} present; ${audit.missing} still missing.`);
for (const [cluster, stats] of clusters) {
  console.log(`- ${cluster}: ${stats.present}/${stats.planned} present`);
}

if (process.argv.includes('--strict') && audit.missing > 0) {
  console.error('\nStrict mode failed; planned links are still missing:');
  for (const row of audit.rows.filter((item) => !item.present)) {
    console.error(`- ${row.source} -> ${row.target}`);
  }
  process.exit(2);
}
