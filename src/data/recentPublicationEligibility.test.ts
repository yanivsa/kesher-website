import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import recentPosts from './postsRecent.json';
import publishedPosts, { isPublishablePost } from './publishedPosts';
import sourceIntent from '../../research/kesher-2026-11-18-source-intent.json';

const targetId = 'couple-conversation-stuck-pursue-withdraw-cycle';
const effectiveIds = new Set(publishedPosts.map((post) => post.id));

describe('recent article production eligibility', () => {
  it.each(recentPosts.map((post) => [post.id, post] as const))(
    '%s is not silently excluded from the public blog',
    (_id, post) => {
      // The website uses this EXACT policy; do not maintain an approximate
      // independent heading or word-count contract in this regression.
      expect(isPublishablePost(post as Parameters<typeof isPublishablePost>[0])).toBe(true);
      expect(effectiveIds.has(post.id)).toBe(true);
      expect(post.title).not.toMatch(/[A-Za-z]/);
      expect(post.excerpt).not.toMatch(/[A-Za-z]/);
      expect(post.content.replace(/<[^>]*>/g, ' ')).not.toMatch(/[A-Za-z]/);
    },
  );

  it('Nov 18 story is represented exactly once with its real original hero', () => {
    const matches = publishedPosts.filter((post) => post.id === targetId);
    expect(matches).toHaveLength(1);
    const post = matches[0];
    expect(post.slug).toBe(targetId);
    expect(post.date).toBe('2026-11-18');
    expect(post.image).toBe('/images/generated/blog/' + targetId + '.jpg');
    expect(post.content.match(/<h3/g)?.length ?? 0).toBeGreaterThanOrEqual(5);

    const file = resolve('public' + post.image);
    const bytes = readFileSync(file);
    expect(bytes.length).toBeGreaterThan(25_000);
    expect(bytes.subarray(0, 3).toString('hex')).toBe('ffd8ff');
    expect(bytes.subarray(-2).toString('hex')).toBe('ffd9');
    expect(sourceIntent.article_slug).toBe(post.id);
    expect(sourceIntent.article_content_sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(sourceIntent.hero.sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(sourceIntent.hero.sha256);
  });
});
