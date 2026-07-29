const LEGACY_HOST = 'shira.saharoni.com';
const PRIMARY_ORIGIN = 'https://kesher.saharoni.com';

const LEGACY_POST_PATH = /^\/\d{4}\/\d{2}\//;
const LEGACY_PAGE_TARGETS: Record<string, string> = {
  '/p/about.html': '/about',
  '/p/contact.html': '/contact',
};

export const legacyRedirectTarget = (requestUrl: string) => {
  const url = new URL(requestUrl);
  if (url.hostname !== LEGACY_HOST) return null;

  const destinationPath =
    LEGACY_POST_PATH.test(url.pathname) || url.pathname.startsWith('/search')
      ? '/blog'
      : LEGACY_PAGE_TARGETS[url.pathname] || '/';

  return `${PRIMARY_ORIGIN}${destinationPath}`;
};

export const canonicalRedirectTarget = (requestUrl: string) => {
  const url = new URL(requestUrl);
  if (url.hostname !== 'kesher.saharoni.com') return null;
  if (url.pathname !== '/b' && url.pathname !== '/b/') return null;
  return `${PRIMARY_ORIGIN}/`;
};

export const onRequest: PagesFunction = async (context) => {
  const redirectTarget =
    canonicalRedirectTarget(context.request.url)
    || legacyRedirectTarget(context.request.url);
  if (redirectTarget) {
    return Response.redirect(redirectTarget, 301);
  }

  return context.next();
};
