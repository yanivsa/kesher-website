import { describe, expect, it } from 'vitest';

import manualPostsOct2026 from './manualPostsOct2026';

const ARTICLE_ID = 'family-chores-quality-time-with-kids';
const EXPECTED_HERO = `/images/generated/blog/${ARTICLE_ID}.png`;

describe('manual October 2026 publication contract', () => {
  it('keeps the family chores article eligible for exact-source hero verification', () => {
    const post = manualPostsOct2026.find((candidate) => candidate.id === ARTICLE_ID) as
      | Record<string, unknown>
      | undefined;

    expect(post).toBeDefined();
    expect(post?.image).toBe(EXPECTED_HERO);
    expect(typeof post?.imageAlt).toBe('string');
    expect((post?.imageAlt as string).length).toBeGreaterThanOrEqual(20);
  });
});
