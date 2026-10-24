import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const { loadPosts } = require('../scripts/load-posts.cjs');
const { buildSitemap } = require('../scripts/generate-sitemap.cjs');
const giftedParentPostsWave2 = require('../src/data/giftedParentPostsWave2.json');

const MANUAL_POST_ID = 'family-chores-quality-time-with-kids';

describe('generated content catalog', () => {
  it('keeps generated assets aligned with every published source catalog', () => {
    const posts = loadPosts();
    const ids = new Set(posts.map((post: { id: string }) => post.id));

    expect(ids.has(MANUAL_POST_ID)).toBe(true);
    for (const post of giftedParentPostsWave2) {
      expect(ids.has(post.id)).toBe(true);
    }
  });

  it('includes the manual parenting article in the sitemap', () => {
    const sitemap = buildSitemap(loadPosts());
    expect(sitemap).toContain(
      `https://kesher.saharoni.com/blog/${MANUAL_POST_ID}`,
    );
  });
});
