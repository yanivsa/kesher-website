const fs = require('fs');
const path = require('path');
const { ROOT, STATIC_ROUTES, isPublishable, blogRoute } = require('./content-policy.cjs');

const posts = JSON.parse(fs.readFileSync(path.join(ROOT, 'src/data/posts.json'), 'utf8'));
const routes = [...STATIC_ROUTES, ...posts.filter(isPublishable).map(blogRoute)];
const errors = [];

for (const route of routes) {
  const file = route === '/'
    ? path.join(ROOT, 'dist/index.html')
    : path.join(ROOT, 'dist', `${route.replace(/^\//, '')}.html`);
  if (!fs.existsSync(file)) {
    errors.push(`Missing prerendered route: ${route}`);
    continue;
  }
  if (route !== '/' && fs.existsSync(path.join(ROOT, 'dist', route.replace(/^\//, ''), 'index.html'))) {
    errors.push(`Route would force a trailing-slash redirect: ${route}`);
  }
  const html = fs.readFileSync(file, 'utf8');
  if (!/<h1[\s>]/.test(html)) errors.push(`Missing h1 in prerendered HTML: ${route}`);
  const descriptions = html.match(/<meta name="description"/g) || [];
  const canonicals = html.match(/<link rel="canonical"/g) || [];
  if (descriptions.length !== 1) errors.push(`Expected one description, found ${descriptions.length}: ${route}`);
  if (canonicals.length !== 1) errors.push(`Expected one canonical, found ${canonicals.length}: ${route}`);
}

const notFound = fs.readFileSync(path.join(ROOT, 'dist/404.html'), 'utf8');
if (!notFound.includes('noindex, nofollow')) errors.push('404 page is not noindex');

const beta = fs.readFileSync(path.join(ROOT, 'dist/b.html'), 'utf8');
if (!beta.includes('noindex, nofollow')) errors.push('Beta page is not noindex');
if (!/<h1[\s>]/.test(beta)) errors.push('Beta page is missing its primary heading');

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(`Verified ${routes.length} prerendered routes and 404.html.`);
