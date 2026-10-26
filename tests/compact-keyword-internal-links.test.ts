import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import publishedPosts from '../src/data/publishedPosts';
import manualRules from '../src/data/internalLinkBackfillManual.json';

const ARTICLE_LINKS = [
  ['healing-after-infidelity', '/couples-counseling-after-infidelity'],
  ['couples-adhd-partner', '/couples-adhd'],
  ['public-tantrums-emotional-regulation', '/parenting-guidance-early-childhood'],
] as const;

const countHref = (html: string, href: string) => {
  const escaped = href.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return (html.match(new RegExp(`href=["']${escaped}["']`, 'g')) || []).length;
};

describe('compact keyword internal-link reinforcement', () => {
  it('links the core service pages contextually to every compact destination', () => {
    const couples = readFileSync(join(process.cwd(), 'src/pages/Services/Couples/CouplesCounseling.tsx'), 'utf8');
    expect(couples).toContain('to="/couples-counseling-after-infidelity"');
    expect(couples).toContain('to="/couples-adhd"');
    expect(couples).toContain('to="/couples-second-chapter"');

    const parenting = readFileSync(join(process.cwd(), 'src/pages/Services/Parenting/ParentingGuidance.tsx'), 'utf8');
    expect(parenting).toContain('to="/parenting-guidance-divorce"');
    expect(parenting).toContain('to="/parenting-guidance-early-childhood"');
  });

  it.each(ARTICLE_LINKS)('%s links exactly once to %s', (source, target) => {
    const post = publishedPosts.find((candidate) => candidate.id === source);
    expect(post, `missing published source: ${source}`).toBeDefined();
    expect(countHref(post!.content, target)).toBe(1);
  });

  it('keeps direct landing-page backfill destinations internal and explicit', () => {
    const rules = manualRules as Array<{ items: Array<{ href?: string }> }>;
    const directHrefs = rules.flatMap((rule) => rule.items.map((item) => item.href).filter(Boolean)) as string[];
    expect(directHrefs).toEqual(expect.arrayContaining(ARTICLE_LINKS.map(([, href]) => href)));
    expect(directHrefs.every((href) => href.startsWith('/') && !href.startsWith('//'))).toBe(true);
  });
});
