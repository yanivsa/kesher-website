import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const { loadPosts } = require('../scripts/load-posts.cjs');

const wave2Ids = [
  'how-to-talk-to-child-about-being-gifted',
  'gifted-child-pressure-to-achieve-parent-guide',
  'gifted-child-bored-at-school-parent-guide',
  'gifted-child-emotional-sensitivity-myths',
];

describe('gifted wave 2 SEO generator catalog', () => {
  it('loads every wave 2 article into the shared generator catalog', () => {
    const ids = new Set(loadPosts().map((post) => post.id));

    for (const id of wave2Ids) {
      expect(ids.has(id), `expected SEO generator catalog to include ${id}`).toBe(true);
    }
  });
});
