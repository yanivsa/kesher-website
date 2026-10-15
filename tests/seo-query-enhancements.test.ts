import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);

type Post = {
  id: string;
  title: string;
  content: string;
  updatedAt?: string;
};

type LoadPostsModule = {
  loadPosts: () => Post[];
};

type ContentPolicyModule = {
  isPublishable: (post: Post) => boolean;
};

const { loadPosts } = require('../scripts/load-posts.cjs') as LoadPostsModule;
const { isPublishable } = require('../scripts/content-policy.cjs') as ContentPolicyModule;

const posts = loadPosts();
const byId = (id: string) => posts.find((post) => post.id === id);

describe('GSC query intent enhancements', () => {
  it('targets the gifted-child query on the existing article', () => {
    const gifted = byId('how-to-identify-a-gifted-child-parents-guide');
    expect(gifted).toBeDefined();
    expect(gifted?.title).toMatch(/^מה זה ילד מחונן\?/u);
    expect(gifted?.content).toMatch(/מה זה ילד מחונן\?/u);
    expect(gifted?.content).toMatch(/איך מוגדרת מחוננות בישראל/u);
    expect(gifted?.updatedAt).toBe('2026-10-15');
  });

  it('targets the age-10 sleep query with a medical escalation boundary', () => {
    const sleep = byId('sleep-needs-10-year-old');
    expect(sleep).toBeDefined();
    expect(sleep?.content).toMatch(/ילדה בת 10 לא נרדמת/u);
    expect(sleep?.content).toMatch(/מתי כדאי לפנות לרופא/u);
    expect(sleep?.updatedAt).toBe('2026-10-15');
  });

  it('targets the early-dating enthusiasm query on the existing article', () => {
    const dating = byId('dating-transition-to-relationship-boundaries');
    expect(dating).toBeDefined();
    expect(dating?.content).toMatch(/האם כדאי לא להראות התלהבות בתחילת קשר\?/u);
    expect(dating?.updatedAt).toBe('2026-10-15');
  });

  it('publishes a dedicated relocation parenting article', () => {
    const relocation = byId('parent-guidance-relocation');
    expect(relocation).toBeDefined();
    expect(relocation?.title).toMatch(/^הדרכת הורים לקראת רילוקיישן/u);
    expect(relocation?.content).toMatch(/מתי לספר לילדים/u);
    expect(relocation?.content).toMatch(/בית ספר חדש/u);
    expect(relocation && isPublishable(relocation)).toBe(true);
  });

  it('keeps post ids unique after merging the enhancement catalog', () => {
    const ids = posts.map((post) => post.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
