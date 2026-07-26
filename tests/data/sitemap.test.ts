import { createRequire } from 'node:module';
import { afterEach, describe, expect, it, vi } from 'vitest';

const require = createRequire(import.meta.url);
const { buildSitemap } = require('../../scripts/generate-sitemap.cjs') as {
  buildSitemap: (posts: Array<{
    id: string;
    date: string;
    content: string;
  }>) => string;
};

const publishableContent = `${'<h3>כותרת</h3>'.repeat(5)}<p>${'מילה '.repeat(500)}</p>`;

afterEach(() => vi.useRealTimers());

describe('sitemap generation', () => {
  it('uses content dates instead of the current clock', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2030-12-31T12:00:00Z'));
    const sitemap = buildSitemap([
      {
        id: 'older-post',
        date: '2026-01-02',
        content: publishableContent,
      },
      {
        id: 'newer-post',
        date: '2026-03-04',
        content: publishableContent,
      },
    ]);

    expect(sitemap).toContain(
      '<loc>https://kesher.saharoni.com/blog</loc>\n    <lastmod>2026-03-04</lastmod>',
    );
    expect(sitemap).toContain(
      '<loc>https://kesher.saharoni.com/blog/older-post</loc>\n    <lastmod>2026-01-02</lastmod>',
    );
    expect(sitemap).not.toContain('2030-12-31');
  });

  it('omits unsupported lastmod dates from static routes', () => {
    const sitemap = buildSitemap([]);
    const homepage = sitemap.match(
      /<loc>https:\/\/kesher\.saharoni\.com\/<\/loc>([\s\S]*?)<\/url>/,
    )?.[1];

    expect(homepage).toBeDefined();
    expect(homepage).not.toContain('<lastmod>');
  });
});
