import { describe, expect, it } from 'vitest';
import publishedPosts from '../src/data/publishedPosts';
import internalLinkPlan from '../scripts/internal-link-plan.json';

const countHref = (html: string, href: string) => {
  const escaped = href.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return (html.match(new RegExp(`href=["']${escaped}["']`, 'g')) || []).length;
};

describe('priority-1 internal-link backfill', () => {
  it('materializes every planned article-to-article link exactly once in published content', () => {
    for (const entry of internalLinkPlan) {
      const post = publishedPosts.find((candidate) => candidate.id === entry.source);
      expect(post, `missing published source: ${entry.source}`).toBeDefined();

      for (const target of entry.targets) {
        const href = `/blog/${target}`;
        expect(
          countHref(post!.content, href),
          `${entry.source} should contain exactly one ${href}`,
        ).toBe(1);
      }
    }
  });
});
