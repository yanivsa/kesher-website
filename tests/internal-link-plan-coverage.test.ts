import { describe, expect, it } from 'vitest';
import publishedPosts from '../src/data/publishedPosts';
import priority1Plan from '../scripts/internal-link-plan.json';
import priority2Plan from '../scripts/internal-link-plan-priority2.json';
import priority3Plan from '../scripts/internal-link-plan-priority3.json';

const plans = [...priority1Plan, ...priority2Plan, ...priority3Plan];

const countTargetHref = (html: string, target: string) => {
  const escapedTarget = target.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const pattern = new RegExp(
    `href=["'](?:https:\\/\\/kesher\\.saharoni\\.com)?\\/blog\\/${escapedTarget}(?:[?#][^"']*)?["']`,
    'g',
  );
  return (html.match(pattern) || []).length;
};

describe('internal-link plan coverage', () => {
  it('references only published source and target articles', () => {
    const publishedIds = new Set(publishedPosts.map((post) => post.id));

    for (const entry of plans) {
      expect(publishedIds.has(entry.source), `missing published source: ${entry.source}`).toBe(true);
      for (const target of entry.targets) {
        expect(target, `${entry.source} contains an empty target`).not.toBe(entry.source);
        expect(publishedIds.has(target), `missing published target: ${target}`).toBe(true);
      }
    }
  });

  it('materializes every planned article-to-article link', () => {
    for (const entry of plans) {
      const post = publishedPosts.find((candidate) => candidate.id === entry.source);
      expect(post, `missing published source: ${entry.source}`).toBeDefined();

      for (const target of entry.targets) {
        expect(
          countTargetHref(post!.content, target),
          `${entry.source} is missing planned /blog/${target}`,
        ).toBeGreaterThanOrEqual(1);
      }
    }
  });

  it('does not plan the same target twice for one source entry', () => {
    for (const entry of plans) {
      expect(new Set(entry.targets).size, `duplicate target in ${entry.source}`).toBe(entry.targets.length);
    }
  });
});
