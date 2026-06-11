const fs = require('fs');
const path = require('path');
const { ROOT, STATIC_ROUTES, isPublishable, blogRoute } = require('./content-policy.cjs');

const posts = JSON.parse(fs.readFileSync(path.join(ROOT, 'src/data/posts.json'), 'utf8'));
const today = new Date().toISOString().slice(0, 10);
const legalRoutes = new Set(['/accessibility', '/privacy', '/terms']);
const serviceRoutes = new Set(['/about', '/contact', '/services/couples', '/services/parenting', '/faq']);
const staticEntries = STATIC_ROUTES.map((route) => ({
  route,
  lastmod: today,
  changefreq: route === '/' || route === '/blog' ? 'weekly' : legalRoutes.has(route) ? 'yearly' : 'monthly',
  priority: route === '/' ? '1.0' : route === '/blog' ? '0.9' : serviceRoutes.has(route) ? '0.8' : '0.3',
}));
const postEntries = posts.filter(isPublishable).map((post) => ({
  route: blogRoute(post),
  lastmod: post.date,
  changefreq: 'monthly',
  priority: '0.7',
}));

const entries = [...staticEntries, ...postEntries]
  .map(({ route, lastmod, changefreq, priority }) => [
    '  <url>',
    `    <loc>https://kesher.saharoni.com${route === '/' ? '/' : route}</loc>`,
    `    <lastmod>${lastmod}</lastmod>`,
    `    <changefreq>${changefreq}</changefreq>`,
    `    <priority>${priority}</priority>`,
    '  </url>',
  ].join('\n'))
  .join('\n');

fs.writeFileSync(
  path.join(ROOT, 'public/sitemap.xml'),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${entries}\n</urlset>\n`,
);
