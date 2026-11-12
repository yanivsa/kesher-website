/** Centralized routes for the parenting-coordination intake funnel. Keep this list aligned with the published topic catalog. */
export const PARENTING_COORDINATION_CONTACT_URL = '/contact?service=parenting_coordination';

export const PARENTING_COORDINATION_ARTICLE_IDS = [
  'what-is-parenting-coordination',
  'parenting-coordination-vs-mediation',
  'divorced-parents-communication',
  'parenting-time-holidays-after-divorce',
  'can-one-parent-start-parenting-coordination',
] as const;

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
