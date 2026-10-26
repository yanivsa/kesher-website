import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import publishedPosts from '../src/data/publishedPosts';
import manualRules from '../src/data/internalLinkBackfillManual.json';

const readSource = (path: string) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

const SERVICE_LINKS = [
  { source: 'src/pages/Services/Couples/CouplesCounseling.tsx', target: '/couples-counseling-after-infidelity' },
  { source: 'src/pages/Services/Couples/CouplesCounseling.tsx', target: '/couples-adhd' },
  { source: 'src/pages/Services/Couples/CouplesCounseling.tsx', target: '/couples-second-chapter' },
  { source: 'src/pages/Services/Parenting/ParentingGuidance.tsx', target: '/parenting-guidance-divorce' },
  { source: 'src/pages/Services/Parenting/ParentingGuidance.tsx', target: '/parenting-guidance-early-childhood' },
] as const;

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
  it.each(SERVICE_LINKS)('$source links contextually to $target', ({ source, target }) => {
    expect(readSource(source)).toContain(`to="${target}"`);
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
