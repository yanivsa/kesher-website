const normalizePath = (pathname: string) =>
  pathname.length > 1 && pathname.endsWith('/')
    ? pathname.slice(0, -1)
    : pathname;

export const shouldHydrateRoute = (
  currentPathname: string,
  canonicalHref: string | undefined,
  hasPrerenderedMarkup: boolean,
  isClientSnapshot = false,
) => {
  // Browser snapshots include settled effects, not React's server render state.
  if (!hasPrerenderedMarkup || !canonicalHref || isClientSnapshot) return false;
  // The interaction-heavy homepage uses pointer and motion preferences at
  // mount time. Preserve its prerendered first paint, then mount a fresh tree
  // so those client-only enhancements cannot create hydration drift.
  if (normalizePath(currentPathname) === '/') return false;

  try {
    const prerenderedPathname = new URL(canonicalHref).pathname;
    return normalizePath(prerenderedPathname) === normalizePath(currentPathname);
  } catch {
    return false;
  }
};
