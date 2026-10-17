import { describe, expect, it } from 'vitest';
import historicalPosts from '../src/data/posts.json';
import recentPosts from '../src/data/postsRecent.json';

const posts = [...recentPosts, ...historicalPosts];

const targets = [
  { id: 'prepare-for-first-grade', keyword: "הכנה לכיתה א" },
  { id: 'first-grade-readiness', keyword: "מוכנות לכיתה א" },
  { id: 'potty-training-age-3-problems', keyword: 'גמילה מחיתולים בגיל 3' },
  { id: 'nighttime-potty-training', keyword: 'גמילה מחיתולים בלילה' },
  { id: 'potty-training-regression', keyword: 'רגרסיה בגמילה מחיתולים' },
];

const stripHtml = (html: string) => html.replace(/<[^>]+>/g, ' ');
const wordCount = (html: string) => stripHtml(html).trim().split(/\s+/).filter(Boolean).length;

for (const target of targets) {
  describe(target.id, () => {
    it('exists as one canonical publishable parenting article', () => {
      const matches = posts.filter((post) => post.id === target.id || post.slug === target.id);
      expect(matches).toHaveLength(1);
      const post = matches[0];
      expect(post.id).toBe(target.id);
      expect(post.slug).toBe(target.id);
      expect(post.title).toContain(target.keyword);
      expect(post.category).toBe('הדרכת הורים');
      expect(post.serviceUrl).toBe('/services/parenting');
      expect(wordCount(post.content)).toBeGreaterThanOrEqual(500);
      expect((post.content.match(/<h3/g) || []).length).toBeGreaterThanOrEqual(5);
      expect(post.content).toContain('/services/parenting');
      expect(post.directAnswer?.trim().length).toBeGreaterThanOrEqual(20);
      expect(Array.isArray(post.evidence)).toBe(true);
      expect(post.evidence.length).toBeGreaterThanOrEqual(2);
    });
  });
}
