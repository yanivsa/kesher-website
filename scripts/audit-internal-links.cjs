const fs = require('fs');
const path = require('path');
const { loadPosts } = require('./load-posts.cjs');
const {
  extractBlogLinks,
  validateInternalLinkPlan,
  auditInternalLinkCoverage,
} = require('./internal-link-policy.cjs');

const planPath = path.join(__dirname, 'internal-link-plan.json');
const backfillPath = path.join(__dirname, '..', 'src', 'data', 'internalLinkBackfill.json');
const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
const backfillRules = fs.existsSync(backfillPath)
  ? JSON.parse(fs.readFileSync(backfillPath, 'utf8'))
  : [];
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
  const rule = backfillRules.find((candidate) => candidate.source === post.id);
  if (!rule || !hasPlacementHeading(post.content, rule.afterHeadingIncludes)) return post;

  const existing = new Set(extractBlogLinks(post.content));
  const overlayLinks = rule.items
    .filter((item) => !existing.has(`/blog/${item.target}`))
    .map((item) => `<a href="/blog/${item.target}">${item.anchor}</a>`)
    .join('');

  return overlayLinks ? { ...post, content: `${post.content}${overlayLinks}` } : post;
});

const audit = auditInternalLinkCoverage(effectivePosts, plan);
const clusters = new Map();
for (const entry of plan) {
  const row = clusters.get(entry.cluster) || { planned: 0, present: 0 };
  const sourceRows = audit.rows.filter((item) => item.source === entry.source);
  row.planned += sourceRows.length;
  row.present += sourceRows.filter((item) => item.present).length;
  clusters.set(entry.cluster, row);
}

console.log(`Internal-link plan valid: ${plan.length} source articles, ${audit.planned} planned article-to-article links.`);
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
