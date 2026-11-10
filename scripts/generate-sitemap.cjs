const fs = require('fs');
const path = require('path');
const { ROOT, STATIC_ROUTES, isPublishable, blogRoute } = require('./content-policy.cjs');
const { loadPosts } = require('./load-posts.cjs');

const legalRoutes = new Set(['/accessibility', '/privacy', '/terms']);
const serviceRoutes = new Set([
  '/about','/now','/friends','/lectures','/contact','/appointment','/services/couples','/services/parenting','/services/mediation','/services/gifted-parenting','/services/aliyah-families','/services/couples-aliyah-relocation','/services/premarital-first-year','/services/late-singleness','/services/finding-relationship','/couples-counseling-ashdod','/parenting-guidance-ashdod','/couples-mediation-ashdod','/parenting-adhd-ashdod','/services/couples/crisis','/services/couples/before-separation','/faq','/faq/when-to-start-couples-counseling','/faq/how-many-couples-counseling-sessions','/faq/does-partner-have-to-come-couples-counseling','/faq/what-to-expect-couples-counseling','/faq/is-couples-counseling-only-for-crisis','/faq/can-trust-be-rebuilt-after-infidelity','/faq/couples-mediation-vs-couples-counseling','/faq/parent-guidance-vs-child-therapy','/faq/what-age-parent-guidance','/faq/parent-guidance-adhd-child','/faq/what-does-premarital-counseling-include','/faq/premarital-counseling-parents-divorced','/faq/premarital-preparation-with-adhd','/faq/when-to-start-premarital-counseling','/faq/first-year-guidance-without-crisis','/faq/premarital-counseling-topics','/faq/couples-counseling-aliyah-relocation-when','/faq/partner-wants-to-return-relocation','/faq/couples-counseling-online-during-relocation','/faq/late-singleness-guidance-who-is-it-for','/faq/late-singleness-counseling-only-for-dating','/faq/guidance-matchmaking-dating-apps','/faq/counseling-at-start-of-new-relationship','/faq/finding-relationship-guidance-includes','/faq/prepare-adhd-child-for-first-grade','/faq/first-grade-preparation-without-adhd','/faq/gifted-child-parent-guidance','/faq/gifted-and-adhd-guidance','/faq/gifted-program-preparation-includes','/faq/guidance-for-aliyah-returning-family','/faq/do-you-work-online','/faq/how-to-book-first-session',
]);
const conversionLandingRoutes = new Set([
  '/couples-counseling-ashdod','/parenting-guidance-ashdod','/couples-mediation-ashdod','/parenting-adhd-ashdod',
  '/couples-counseling-after-infidelity','/parenting-guidance-divorce','/parenting-guidance-early-childhood','/couples-adhd','/couples-second-chapter',
]);
const noindexRoutes = new Set(['/thank-you-booked','/thank-you-contact','/couples-crisis-ashdod','/couples-counseling-gan-yavne']);
const buildSitemap = (posts) => {
  const published = posts.filter(isPublishable);
  const newestPostDate = published.reduce((latest, post) => { const effectiveDate = (post.updatedAt && post.updatedAt > post.date) ? post.updatedAt : post.date; return effectiveDate > latest ? effectiveDate : latest; }, '');
  const staticEntries = STATIC_ROUTES.filter((route) => !noindexRoutes.has(route)).map((route) => ({ route, lastmod: route === '/blog' ? newestPostDate : '', changefreq: route === '/' || route === '/blog' ? 'weekly' : legalRoutes.has(route) ? 'yearly' : 'monthly', priority: route === '/' ? '1.0' : conversionLandingRoutes.has(route) ? '0.95' : route === '/blog' ? '0.9' : serviceRoutes.has(route) ? '0.8' : '0.3' }));
  const postEntries = published.map((post) => ({ route: blogRoute(post), lastmod: (post.updatedAt && typeof post.updatedAt === 'string' && post.updatedAt.trim()) ? post.updatedAt.trim() : post.date, changefreq: 'monthly', priority: '0.7' }));
  const entries = [...staticEntries, ...postEntries].map(({ route, lastmod, changefreq, priority }) => ['  <url>',`    <loc>https://kesher.saharoni.com${route === '/' ? '' : route}</loc>`,...(lastmod ? [`    <lastmod>${lastmod}</lastmod>`] : []),`    <changefreq>${changefreq}</changefreq>`,`    <priority>${priority}</priority>`,'  </url>'].join('\n')).join('\n');
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${entries}\n</urlset>\n`;
};
if (require.main === module) { const posts = loadPosts(); fs.writeFileSync(path.join(ROOT, 'public/sitemap.xml'), buildSitemap(posts)); }
module.exports = { buildSitemap };
