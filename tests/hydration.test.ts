import { describe, expect, it } from 'vitest';
import { shouldHydrateRoute } from '../src/lib/hydration';

describe('route hydration', () => {
  it('mounts settled browser snapshots while retaining hydration for matching server markup', () => {
    expect(shouldHydrateRoute('/blog/sleep-needs-10-year-old',
      'https://kesher.saharoni.com/blog/sleep-needs-10-year-old', true, true)).toBe(false);
    expect(shouldHydrateRoute('/blog/sleep-needs-10-year-old',
      'https://kesher.saharoni.com/blog/sleep-needs-10-year-old', true, false)).toBe(true);
  });

  it('hydrates markup only when its canonical route matches the request', () => {
    expect(shouldHydrateRoute(
      '/about',
      'https://kesher.saharoni.com/about',
      true,
    )).toBe(true);
    expect(shouldHydrateRoute(
      '/blog/missing-post',
      'https://kesher.saharoni.com',
      true,
    )).toBe(false);
  });

  it('normalizes trailing slashes and rejects missing markup', () => {
    expect(shouldHydrateRoute(
      '/about/',
      'https://kesher.saharoni.com/about',
      true,
    )).toBe(true);
    expect(shouldHydrateRoute(
      '/about',
      'https://kesher.saharoni.com/about',
      false,
    )).toBe(false);
  });

  it('mounts the interaction-heavy homepage as a fresh client tree', () => {
    expect(shouldHydrateRoute(
      '/',
      'https://kesher.saharoni.com',
      true,
    )).toBe(false);
  });
});
