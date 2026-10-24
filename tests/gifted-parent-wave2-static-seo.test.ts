import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const { loadPosts } = require('../scripts/load-posts.cjs') as {
  loadPosts: () => Array<{ id?: string }>;
};

const wave2Ids = [
  'how-to-talk-to-child-about-being-gifted',
  'gifted-child-pressure-to-achieve-parent-guide',
  'gifted-child-bored-at-school-parent-guide',
  'gifted-child-emotional-sensitivity-myths',
];

describe('gifted parenting wave 2 static SEO catalog', () => {
  it('loads every wave 2 article into the catalog used by generated SEO assets', () => {
    const ids = new Set(loadPosts().map((post) => post.id));

    for (const id of wave2Ids) {
      expect(ids.has(id), `${id} should be available to sitemap/RSS/prerender generators`).toBe(true);
    }
  });
});
