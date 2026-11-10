import { describe, expect, it } from 'vitest';

import giftedParentPosts from './giftedParentPosts.json';
import giftedParentPostsWave2 from './giftedParentPostsWave2.json';
import manualPostsOct2026 from './manualPostsOct2026';
import posts from './posts.json';
import postsRecent from './postsRecent.json';

const TARGET_IDS = [
  'gifted-test-first-emotional-preparation-parents',
  'child-not-selected-gifted-program-parent-response',
  'after-gifted-identification-next-steps-family',
  'how-to-talk-to-child-about-being-gifted',
  'gifted-child-pressure-to-achieve-parent-guide',
  'gifted-child-bored-at-school-parent-guide',
  'gifted-child-emotional-sensitivity-myths',
  'child-argues-every-request-boundaries',
  'child-meltdown-after-school',
  'prepare-for-first-grade',
  'first-grade-readiness',
  'potty-training-age-3-problems',
  'nighttime-potty-training',
  'potty-training-regression',
  'child-refuses-homework',
  'premarital-counseling-divorced-parents',
] as const;

type PostRow = {
  id?: string;
  image?: string;
  imageAlt?: string;
};

const authoritative = [
  ...(manualPostsOct2026 as PostRow[]),
  ...(giftedParentPosts as PostRow[]),
  ...(giftedParentPostsWave2 as PostRow[]),
];
const authoritativeIds = new Set(authoritative.map((post) => post.id));
const effectiveCatalog = [
  ...authoritative,
  ...(postsRecent as PostRow[]).filter((post) => !authoritativeIds.has(post.id)),
  ...(posts as PostRow[]).filter((post) => !authoritativeIds.has(post.id)),
];

describe('publication hero exact-source coverage', () => {
  it.each(TARGET_IDS)('%s has an authoritative generated article hero', (id) => {
    const matches = effectiveCatalog.filter((post) => post.id === id);
    expect(matches).toHaveLength(1);
    expect(matches[0]?.image).toMatch(/^\/images\/generated\/blog\/[^/]+\.(?:png|jpe?g|webp)$/i);
    expect(matches[0]?.imageAlt).toMatch(/[\u0590-\u05FF]/);
    expect((matches[0]?.imageAlt ?? '').length).toBeGreaterThanOrEqual(20);
  });
});
