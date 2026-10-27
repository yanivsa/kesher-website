const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const STATIC_ROUTES = [
  '/', '/about', '/now', '/friends', '/links', '/lectures', '/contact', '/appointment',
  '/services/couples', '/services/parenting', '/services/mediation', '/services/gifted-parenting',
  '/services/aliyah-families', '/services/couples-aliyah-relocation', '/services/premarital-first-year',
  '/services/late-singleness', '/services/finding-relationship', '/blog', '/faq',
  '/faq/when-to-start-couples-counseling', '/faq/how-many-couples-counseling-sessions', '/faq/does-partner-have-to-come-couples-counseling', '/faq/what-to-expect-couples-counseling', '/faq/is-couples-counseling-only-for-crisis', '/faq/can-trust-be-rebuilt-after-infidelity', '/faq/couples-mediation-vs-couples-counseling', '/faq/parent-guidance-vs-child-therapy', '/faq/what-age-parent-guidance', '/faq/parent-guidance-adhd-child',
  '/faq/what-does-premarital-counseling-include', '/faq/premarital-counseling-parents-divorced', '/faq/premarital-preparation-with-adhd', '/faq/when-to-start-premarital-counseling', '/faq/first-year-guidance-without-crisis', '/faq/premarital-counseling-topics', '/faq/couples-counseling-aliyah-relocation-when', '/faq/partner-wants-to-return-relocation', '/faq/couples-counseling-online-during-relocation', '/faq/late-singleness-guidance-who-is-it-for', '/faq/late-singleness-counseling-only-for-dating', '/faq/guidance-matchmaking-dating-apps', '/faq/counseling-at-start-of-new-relationship', '/faq/finding-relationship-guidance-includes', '/faq/prepare-adhd-child-for-first-grade', '/faq/first-grade-preparation-without-adhd', '/faq/gifted-child-parent-guidance', '/faq/gifted-and-adhd-guidance', '/faq/gifted-program-preparation-includes', '/faq/guidance-for-aliyah-returning-family', '/faq/do-you-work-online', '/faq/how-to-book-first-session',
  '/couples-counseling-ashdod', '/parenting-guidance-ashdod', '/couples-mediation-ashdod',
  '/couples-crisis-ashdod', '/parenting-adhd-ashdod', '/couples-counseling-gan-yavne',
  '/couples-counseling-after-infidelity', '/parenting-guidance-divorce',
  '/parenting-guidance-early-childhood', '/couples-adhd', '/couples-second-chapter',
  '/services/couples/crisis', '/services/couples/before-separation', '/thank-you-booked',
  '/thank-you-contact', '/accessibility', '/privacy', '/terms',
];

const stripHtml = (html) => html.replace(/<[^>]+>/g, ' ');
const wordCount = (html) => stripHtml(html).trim().split(/\s+/).filter(Boolean).length;
const headingCount = (html) => (html.match(/<h3/g) || []).length;
const isPublishable = (post) => wordCount(post.content) >= 500 && headingCount(post.content) >= 5;
const blogRoute = (post) => `/blog/${post.id}`;

module.exports = { ROOT, STATIC_ROUTES, stripHtml, wordCount, headingCount, isPublishable, blogRoute };
