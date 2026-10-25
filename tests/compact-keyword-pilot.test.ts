import { describe, expect, it } from 'vitest';
import { LANDING_PAGES_CONFIG } from '../src/data/landingPagesConfig';
import { preloadRoute } from '../src/App';

const PILOTS = [
  ['couples-after-infidelity', '/couples-counseling-after-infidelity', 'ייעוץ זוגי אחרי בגידה'],
  ['parenting-divorce', '/parenting-guidance-divorce', 'הדרכת הורים בזמן פרידה וגירושין'],
  ['parenting-early-childhood', '/parenting-guidance-early-childhood', 'הדרכת הורים לגיל הרך'],
  ['couples-adhd', '/couples-adhd', 'ייעוץ זוגי'],
  ['couples-second-chapter', '/couples-second-chapter', 'ייעוץ זוגי לפרק ב׳'],
] as const;

describe('compact keyword pilot', () => {
  it.each(PILOTS)('%s owns a distinct indexable landing-page intent', (key, slug, query) => {
    const config = LANDING_PAGES_CONFIG[key];
    expect(config).toBeDefined();
    expect(config.slug).toBe(slug);
    expect(config.meta.canonicalUrl).toBe(`https://kesher.saharoni.com${slug}`);
    expect(config.meta.noIndex).not.toBe(true);
    expect(config.meta.robots || '').not.toContain('noindex');
    expect(`${config.meta.title} ${config.hero.headline}`).toContain(query);
    expect(config.hero.trustPoints.length).toBeGreaterThanOrEqual(3);
    expect(config.painPoints.items.length).toBeGreaterThanOrEqual(4);
    expect(config.approach.steps.length).toBeGreaterThanOrEqual(3);
    expect(config.faq.items.length).toBeGreaterThanOrEqual(4);
    expect(config.relatedService.href).toMatch(/^\/services\//);
  });

  it('preloads every pilot route with its own loader', async () => {
    const promises = PILOTS.map(([, slug]) => preloadRoute(slug));
    expect(new Set(promises).size).toBe(PILOTS.length);
    await Promise.all(promises);
  });
});
