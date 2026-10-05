const fs = require('fs');
const path = require('path');
const { ROOT, STATIC_ROUTES, isPublishable, blogRoute } = require('./content-policy.cjs');

const posts = JSON.parse(fs.readFileSync(path.join(ROOT, 'src/data/posts.json'), 'utf8'));
const routes = [...STATIC_ROUTES, ...posts.filter(isPublishable).map(blogRoute)];
const errors = [];
const canonicalTargets = new Map();
const SITE_ORIGIN = 'https://kesher.saharoni.com';
const hasNonAscii = (value) => /[^\x00-\x7F]/.test(value);

for (const route of routes) {
  const clean = route.replace(/^\//, '');
  const isUnicodeBlogRoute = route.startsWith('/blog/') && hasNonAscii(route);
  const file = route === '/'
    ? path.join(ROOT, 'dist/index.html')
    : isUnicodeBlogRoute
      ? path.join(ROOT, 'dist', clean, 'index.html')
      : path.join(ROOT, 'dist', `${clean}.html`);

  if (!fs.existsSync(file)) {
    errors.push(`Missing prerendered route: ${route}`);
    continue;
  }

  if (!isUnicodeBlogRoute && route !== '/' && fs.existsSync(path.join(ROOT, 'dist', clean, 'index.html'))) {
    errors.push(`Unexpected directory-index route: ${route}`);
  }

  const html = fs.readFileSync(file, 'utf8');
  if (!/<h1[\s>]/.test(html)) errors.push(`Missing h1 in prerendered HTML: ${route}`);
  const descriptions = html.match(/<meta name="description"/g) || [];
  const canonicalTags = html.match(/<link\b[^>]*\brel=["']canonical["'][^>]*>/gi) || [];
  if (descriptions.length !== 1) errors.push(`Expected one description, found ${descriptions.length}: ${route}`);
  if (canonicalTags.length !== 1) {
    errors.push(`Expected one canonical, found ${canonicalTags.length}: ${route}`);
  } else {
    const canonicalHref = canonicalTags[0].match(/\bhref=["']([^"']+)["']/i)?.[1];
    const expectedCanonical = `${SITE_ORIGIN}${route === '/' ? '' : route}`;
    if (!canonicalHref) {
      errors.push(`Canonical is missing href: ${route}`);
    } else {
      if (canonicalHref !== expectedCanonical) {
        errors.push(`Canonical mismatch: ${route} -> ${canonicalHref}; expected ${expectedCanonical}`);
      }
      const previousRoute = canonicalTargets.get(canonicalHref);
      if (previousRoute && previousRoute !== route) {
        errors.push(`Duplicate canonical target: ${canonicalHref} used by ${previousRoute} and ${route}`);
      } else {
        canonicalTargets.set(canonicalHref, route);
      }
    }
  }
}

const todaysUnicodeBlog = posts
  .filter(isPublishable)
  .map(blogRoute)
  .filter((route) => route.startsWith('/blog/') && hasNonAscii(route));
if (todaysUnicodeBlog.length === 0) {
  console.warn('No Unicode blog routes were available to exercise the Cloudflare directory-index contract.');
}

const notFound = fs.readFileSync(path.join(ROOT, 'dist/404.html'), 'utf8');
if (!notFound.includes('noindex, nofollow')) errors.push('404 page is not noindex');

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(`Verified ${routes.length} prerendered routes with self-canonicals and 404.html.`);
