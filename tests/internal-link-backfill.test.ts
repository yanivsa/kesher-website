import { describe, expect, it } from 'vitest';
import publishedPosts from '../src/data/publishedPosts';
import internalLinkPlan from '../scripts/internal-link-plan.json';

const countTargetHref = (html: string, target: string) => {
  const escapedTarget = target.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(
    `href=["'](?:https:\\/\\/kesher\\.saharoni\\.com)?\\/blog\\/${escapedTarget}(?:[?#][^"']*)?["']`,
    'g',
  );
  return (html.match(pattern) || []).length;
};

describe('priority-1 internal-link backfill', () => {
  it('materializes every planned article-to-article link exactly once in published content', () => {
    for (const entry of internalLinkPlan) {
      const post = publishedPosts.find((candidate) => candidate.id === entry.source);
      expect(post, `missing published source: ${entry.source}`).toBeDefined();

      for (const target of entry.targets) {
        expect(
          countTargetHref(post!.content, target),
          `${entry.source} should contain exactly one /blog/${target}`,
        ).toBe(1);
      }
    }
  });
});
