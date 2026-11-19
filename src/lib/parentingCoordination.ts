/** Centralized routes for the parenting-coordination intake funnel. Published article paths are derived from the canonical catalog. */
import publishedCoordinationIds from '../data/parentingCoordinationArticleIds.json';

export const PARENTING_COORDINATION_CONTACT_URL = '/contact?service=parenting_coordination';

// This tiny manifest is generated from all published canonical posts during
// npm run generate. Never bundle the full longform article JSON in the shared
// Header/Footer/mobile-sticky navigation just to decide specialty intake.
export const PARENTING_COORDINATION_ARTICLE_IDS: readonly string[] = publishedCoordinationIds;

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
