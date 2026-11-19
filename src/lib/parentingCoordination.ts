/** Centralized routes for the parenting-coordination intake funnel. Published article paths are derived from the canonical catalog. */
import parentingCoordinationPosts from '../data/parentingCoordinationPosts.json';

export const PARENTING_COORDINATION_CONTACT_URL = '/contact?service=parenting_coordination';

// Never keep a second manually maintained list: new published guides must
// inherit pre-screening and privacy-conscious contact CTAs automatically.
export const PARENTING_COORDINATION_ARTICLE_IDS: readonly string[] = parentingCoordinationPosts.map(post => post.id);

const articlePaths = new Set<string>(
  PARENTING_COORDINATION_ARTICLE_IDS.map(id => `/blog/${id}`),
);

export const isParentingCoordinationPath = (pathname: string, search = ''): boolean => {
  const normalized = pathname.length > 1 ? pathname.replace(/\/$/, '') : pathname;
  const isDedicatedIntake = normalized === '/contact'
    && new URLSearchParams(search).get('service') === 'parenting_coordination';
  return isDedicatedIntake
    || normalized === '/services/parenting-coordination'
    || normalized === '/blog/category/parenting-coordination'
    || articlePaths.has(normalized);
};

export const PARENTING_COORDINATION_WHATSAPP_MESSAGE = 'שלום שירה, אשמח למידע על בירור התאמה לתיאום הורי. אפשר לחזור אליי?';
