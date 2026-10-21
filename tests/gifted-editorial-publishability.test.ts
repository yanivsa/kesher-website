import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const { loadPosts } = require('../scripts/load-posts.cjs');
const { isPublishable, wordCount, headingCount } = require('../scripts/content-policy.cjs');

const editorialIds = [
  'how-to-talk-to-child-about-being-gifted',
  'gifted-test-accepted-what-next',
  'gifted-test-not-accepted-parent-response',
  'gifted-test-emotional-preparation',
];

describe('gifted parenting editorial production contract', () => {
  it('keeps every editorial gifted-parenting article above the public quality gate', () => {
    const posts = loadPosts();

    for (const id of editorialIds) {
      const post = posts.find((row: { id?: string }) => row.id === id);
      expect(post, `${id} should exist`).toBeDefined();
      expect(
        isPublishable(post),
        `${id} must be publishable (words=${wordCount(post.content)}, h3=${headingCount(post.content)})`,
      ).toBe(true);
    }
  });
});
