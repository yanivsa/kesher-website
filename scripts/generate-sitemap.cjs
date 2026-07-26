const fs = require('fs');
const path = require('path');
const { ROOT, STATIC_ROUTES, isPublishable, blogRoute } = require('./content-policy.cjs');

const legalRoutes = new Set(['/accessibility', '/privacy', '/terms']);
const serviceRoutes = new Set([
  '/about',
  '/contact',
  '/appointment',
  '/services/couples',
  '/services/parenting',
  '/services/mediation',
  '/services/gifted-parenting',
  '/services/aliyah-families',
  '/services/late-singleness',
  '/services/finding-relationship',
  '/faq',
]);
const buildSitemap = (posts) => {
  const published = posts.filter(isPublishable);
  const newestPostDate = published.reduce(
    (latest, post) => post.date > latest ? post.date : latest,
    '',
  );
  const staticEntries = STATIC_ROUTES.map((route) => ({
    route,
    lastmod: route === '/blog' ? newestPostDate : '',
    changefreq: route === '/' || route === '/blog' ? 'weekly' : legalRoutes.has(route) ? 'yearly' : 'monthly',
    priority: route === '/' ? '1.0' : route === '/blog' ? '0.9' : serviceRoutes.has(route) ? '0.8' : '0.3',
  }));
  const postEntries = published.map((post) => ({
    route: blogRoute(post),
    lastmod: post.date,
    changefreq: 'monthly',
    priority: '0.7',
  }));

  const entries = [...staticEntries, ...postEntries]
    .map(({ route, lastmod, changefreq, priority }) => [
      '  <url>',
      `    <loc>https://kesher.saharoni.com${route === '/' ? '/' : route}</loc>`,
      ...(lastmod ? [`    <lastmod>${lastmod}</lastmod>`] : []),
      `    <changefreq>${changefreq}</changefreq>`,
      `    <priority>${priority}</priority>`,
      '  </url>',
    ].join('\n'))
    .join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${entries}\n</urlset>\n`;
};

if (require.main === module) {
  const posts = JSON.parse(fs.readFileSync(path.join(ROOT, 'src/data/posts.json'), 'utf8'));
  fs.writeFileSync(path.join(ROOT, 'public/sitemap.xml'), buildSitemap(posts));
}

module.exports = { buildSitemap };
