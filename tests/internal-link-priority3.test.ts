import { describe, expect, it } from 'vitest';
import publishedPosts from '../src/data/publishedPosts';
import priority3Plan from '../scripts/internal-link-plan-priority3.json';

const countTargetHref = (html: string, target: string) => {
  const escapedTarget = target.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(
    `href=["'](?:https:\\/\\/kesher\\.saharoni\\.com)?\\/blog\\/${escapedTarget}(?:[?#][^"']*)?["']`,
    'g',
  );
  return (html.match(pattern) || []).length;
};

describe('priority-3 internal-link backfill', () => {
  it('keeps the first tranche intentionally sparse', () => {
    expect(priority3Plan).toHaveLength(4);
    for (const entry of priority3Plan) {
      expect(entry.targets).toHaveLength(1);
    }
  });

  it('references only published source and target articles', () => {
    const publishedIds = new Set(publishedPosts.map((post) => post.id));
    for (const entry of priority3Plan) {
      expect(publishedIds.has(entry.source), `missing published source: ${entry.source}`).toBe(true);
      for (const target of entry.targets) {
        expect(publishedIds.has(target), `missing published target: ${target}`).toBe(true);
      }
    }
  });

  it('materializes every planned Priority-3 article link exactly once', () => {
    for (const entry of priority3Plan) {
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
