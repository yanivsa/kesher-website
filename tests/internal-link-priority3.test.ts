import { describe, expect, it } from 'vitest';
import publishedPosts from '../src/data/publishedPosts';
import priority3Plan from '../scripts/internal-link-plan-priority3.json';
import cannibalizationHolds from '../scripts/internal-link-cannibalization-holds.json';

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
    expect(priority3Plan).toHaveLength(2);
    for (const entry of priority3Plan) {
      expect(entry.targets).toHaveLength(1);
      expect(entry.priority).toBe(3);
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

  it('does not strengthen pages on an active cannibalization hold', () => {
    const heldSlugs = new Set(
      cannibalizationHolds
        .filter((hold) => hold.status === 'hold')
        .flatMap((hold) => hold.slugs),
    );

    for (const entry of priority3Plan) {
      expect(heldSlugs.has(entry.source), `${entry.source} is on a cannibalization hold`).toBe(false);
      for (const target of entry.targets) {
        expect(heldSlugs.has(target), `${target} is on a cannibalization hold`).toBe(false);
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
