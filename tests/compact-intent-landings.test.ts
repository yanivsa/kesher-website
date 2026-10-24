import { createRequire } from 'node:module';
import fs from 'node:fs';
import { describe, expect, it } from 'vitest';
import { LANDING_PAGES_CONFIG } from '../src/data/landingPagesConfig';
import { inferServiceType } from '../src/lib/analytics';

const require = createRequire(import.meta.url);
const { buildSitemap } = require('../scripts/generate-sitemap.cjs') as {
  buildSitemap: (posts: Array<{ id: string; date: string; content: string }>) => string;
};

const pilots = [
  ['couples-counseling-after-infidelity', 'couples_infidelity', '/services/couples'],
  ['parenting-guidance-divorce', 'parenting_divorce', '/services/parenting'],
  ['parenting-guidance-early-childhood', 'parenting_early_childhood', '/services/parenting'],
  ['couples-adhd', 'couples_adhd', '/services/couples'],
  ['couples-second-chapter', 'couples_second_chapter', '/services/couples'],
] as const;

describe('new-intent compact landing pilot contract', () => {
  it.each(pilots)('defines indexable config for %s', (key, serviceType, parentService) => {
    const config = LANDING_PAGES_CONFIG[key];
    expect(config).toBeDefined();
    expect(config.slug).toBe(`/${key}`);
    expect(config.serviceType).toBe(serviceType);
    expect(config.meta.canonicalUrl).toBe(`https://kesher.saharoni.com/${key}`);
    expect(config.meta.noIndex).not.toBe(true);
    expect(config.meta.robots || '').not.toContain('noindex');
    expect(config.relatedService.href).toBe(parentService);
    expect(config.faq.items.length).toBeGreaterThanOrEqual(4);
  });

  it('publishes all five pilots in the generated sitemap', () => {
    const sitemap = buildSitemap([]);
    pilots.forEach(([key]) => {
      expect(sitemap).toContain(`<loc>https://kesher.saharoni.com/${key}</loc>`);
    });
  });

  it('wires each pilot into app routing and standalone landing layout', () => {
    const appSource = fs.readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
    const layoutSource = fs.readFileSync(new URL('../src/components/Layout/Layout.tsx', import.meta.url), 'utf8');
    pilots.forEach(([key]) => {
      expect(appSource).toContain(`path=\"/${key}\"`);
      expect(layoutSource).toContain(`cleanPath === '/${key}'`);
    });
  });

  it.each(pilots)('classifies analytics for %s', (key, serviceType) => {
    expect(inferServiceType(`/${key}`)).toBe(serviceType);
    expect(inferServiceType(`/${key}/`)).toBe(serviceType);
  });
});
