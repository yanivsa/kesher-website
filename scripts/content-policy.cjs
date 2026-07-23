const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const STATIC_ROUTES = [
  '/',
  '/about',
  '/contact',
  '/appointment',
  '/services/couples',
  '/services/parenting',
  '/services/mediation',
  '/services/gifted-parenting',
  '/services/aliyah-families',
  '/blog',
  '/faq',
  '/accessibility',
  '/privacy',
  '/terms',
];

const stripHtml = (html) => html.replace(/<[^>]+>/g, ' ');
const wordCount = (html) => stripHtml(html).trim().split(/\s+/).filter(Boolean).length;
const headingCount = (html) => (html.match(/<h3/g) || []).length;
const isPublishable = (post) => wordCount(post.content) >= 500 && headingCount(post.content) >= 5;
const blogRoute = (post) => `/blog/${post.id}`;

module.exports = {
  ROOT,
  STATIC_ROUTES,
  stripHtml,
  wordCount,
  headingCount,
  isPublishable,
  blogRoute,
};
