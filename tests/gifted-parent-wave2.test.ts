import { describe, expect, it } from 'vitest';
import publishedPosts, { isPublishablePost } from '../src/data/publishedPosts';

const wave2Ids = [
  'how-to-talk-to-child-about-being-gifted',
  'gifted-child-pressure-to-achieve-parent-guide',
  'gifted-child-bored-at-school-parent-guide',
  'gifted-child-emotional-sensitivity-myths',
];

describe('gifted parenting topic cluster wave 2', () => {
  it('publishes every wave 2 article exactly once', () => {
    for (const id of wave2Ids) {
      const matches = publishedPosts.filter((post) => post.id === id);
      expect(matches).toHaveLength(1);
      expect(isPublishablePost(matches[0])).toBe(true);
    }
  });

  it('keeps every wave 2 article focused on the parental cluster and linked to the pillar', () => {
    for (const id of wave2Ids) {
      const post = publishedPosts.find((row) => row.id === id);
      expect(post).toBeDefined();
      expect(post?.category).toBe('הדרכת הורים');
      expect(post?.controllerManaged).toBe(false);
      expect(post?.content).toContain('/blog/how-to-identify-a-gifted-child-parents-guide');
    }
  });

  it('links the pillar back to every wave 2 article', () => {
    const pillar = publishedPosts.find((row) => row.id === 'how-to-identify-a-gifted-child-parents-guide');
    const relatedPostIds = pillar && 'relatedPostIds' in pillar && Array.isArray(pillar.relatedPostIds)
      ? pillar.relatedPostIds
      : [];

    for (const id of wave2Ids) {
      expect(relatedPostIds).toContain(id);
    }
  });

  it('keeps authoritative evidence on each wave 2 article', () => {
    for (const id of wave2Ids) {
      const post = publishedPosts.find((row) => row.id === id);
      const evidence = post && 'evidence' in post && Array.isArray(post.evidence) ? post.evidence : [];
      const urls = evidence.map((item) => item.url).filter(Boolean).join(' ');
      expect(evidence.length).toBeGreaterThanOrEqual(2);
      expect(urls).toMatch(/nagc\.org|education\.gov\.il|gov\.il|health\.gov\.il/);
    }
  });

  it('does not target test-prep query intent', () => {
    for (const id of wave2Ids) {
      const post = publishedPosts.find((row) => row.id === id);
      const targeting = `${post?.title ?? ''} ${(post?.tags ?? []).join(' ')}`;
      expect(targeting).not.toMatch(/שאלות לדוגמה|קורס מחוננים|הכנה לשלב ב|מכון הכנה/);
    }
  });
});
