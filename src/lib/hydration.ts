const normalizePath = (pathname: string) =>
  pathname.length > 1 && pathname.endsWith('/')
    ? pathname.slice(0, -1)
    : pathname;

export const shouldHydrateRoute = (
  currentPathname: string,
  canonicalHref: string | undefined,
  hasPrerenderedMarkup: boolean,
) => {
  if (!hasPrerenderedMarkup || !canonicalHref) return false;

  try {
    const prerenderedPathname = new URL(canonicalHref).pathname;
    return normalizePath(prerenderedPathname) === normalizePath(currentPathname);
  } catch {
    return false;
  }
};
