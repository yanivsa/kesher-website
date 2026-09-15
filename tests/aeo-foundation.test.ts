import { describe, expect, it } from 'vitest';
import { SITE_CONFIG } from '../src/constants/siteConfig';
import { buildSitemap } from '../scripts/generate-sitemap.cjs';

describe('AEO Foundation — Canonical Entity & Structured Data', () => {
  it('confirms canonical Shira Person ID and author URL in SITE_CONFIG', () => {
    expect(SITE_CONFIG.author).toBe('שירה סהרוני');
    expect(SITE_CONFIG.url).toBe('https://kesher.saharoni.com');
  });

  it('generates truthful sitemap lastmod using updatedAt when present and date otherwise', () => {
    const mockPosts = [
      {
        id: 'post-with-update',
        title: 'מאמר מעודכן עם תאריך אמת',
        date: '2026-06-01',
        updatedAt: '2026-09-15',
        category: 'זוגיות',
        content: '<h3>כותרת 1</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 2</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 3</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 4</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 5</h3><p>' + 'מילה '.repeat(150) + '</p>',
      },
      {
        id: 'post-without-update',
        title: 'מאמר מקורי ללא עדכון',
        date: '2026-05-10',
        category: 'הדרכת הורים',
        content: '<h3>כותרת 1</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 2</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 3</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 4</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 5</h3><p>' + 'מילה '.repeat(150) + '</p>',
      }
    ];

    const xml = buildSitemap(mockPosts);
    expect(xml).toContain('<loc>https://kesher.saharoni.com/blog/post-with-update</loc>');
    expect(xml).toContain('<lastmod>2026-09-15</lastmod>');
    expect(xml).toContain('<loc>https://kesher.saharoni.com/blog/post-without-update</loc>');
    expect(xml).toContain('<lastmod>2026-05-10</lastmod>');
  });
});
