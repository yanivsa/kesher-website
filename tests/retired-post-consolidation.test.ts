import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import publishedPosts from '../src/data/publishedPosts';
import cannibalizationHolds from '../scripts/internal-link-cannibalization-holds.json';

const require = createRequire(import.meta.url);
const { loadPosts } = require('../scripts/load-posts.cjs');
const { buildSitemap } = require('../scripts/generate-sitemap.cjs');

const retiredSlug = 'late-singleness-friends-moving-forward';
const canonicalSlug = 'older-singles-friendship-changes-loneliness';

describe('late-singlehood cannibalization consolidation', () => {
  it('retires the overlapping article from all generated publication surfaces', () => {
    expect(publishedPosts.some((post) => post.id === retiredSlug)).toBe(false);

    const generatedPosts = loadPosts();
    expect(generatedPosts.some((post: { id?: string }) => post.id === retiredSlug)).toBe(false);
    expect(generatedPosts.some((post: { id?: string }) => post.id === canonicalSlug)).toBe(true);

    const sitemap = buildSitemap(generatedPosts);
    expect(sitemap).not.toContain(`/blog/${retiredSlug}`);
    expect(sitemap).toContain(`/blog/${canonicalSlug}`);
  });

  it('redirects the retired URL permanently to the surviving friendship article', () => {
    const redirects = readFileSync(new URL('../public/_redirects', import.meta.url), 'utf8');
    expect(redirects).toContain(`/blog/${retiredSlug} /blog/${canonicalSlug} 301`);
  });

  it('marks the cannibalization hold as resolved after consolidation', () => {
    const cluster = cannibalizationHolds.find((hold) => hold.cluster === 'late-singlehood-friendship');
    expect(cluster).toBeDefined();
    expect(cluster?.status).toBe('resolved');
  });
});
