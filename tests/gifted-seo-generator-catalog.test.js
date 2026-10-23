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
  it('loads every wave 2 article exactly once into the shared generator catalog', () => {
    const posts = loadPosts();

    for (const id of wave2Ids) {
      expect(posts.filter((post) => post.id === id), `expected one SEO generator entry for ${id}`).toHaveLength(1);
    }
  });

  it('keeps the full generator catalog free of duplicate ids', () => {
    const ids = loadPosts().map((post) => post.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
