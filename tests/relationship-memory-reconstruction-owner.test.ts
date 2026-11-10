import { describe, expect, it } from 'vitest';
import publishedPosts, { isPublishablePost } from '../src/data/publishedPosts';

const SOURCE_SLUG = 'relationship-memory-reconstruction';
const SOURCE_IMAGE = '/images/generated/blog/relationship-memory-reconstruction-editorial-20261106.jpg';

describe('owner KESHER relationship memory source identity', () => {
  const matching = publishedPosts.filter((post) => post.id === SOURCE_SLUG);
  const post = matching[0];

  it('contains exactly one publishable source with stable owner identity', () => {
    expect(matching).toHaveLength(1);
    expect(isPublishablePost(post)).toBe(true);
    expect(post.slug).toBe(SOURCE_SLUG);
    expect(post.controllerManaged).toBe(true);
    expect(post.category).toBe('ייעוץ זוגי');
    expect(post.serviceUrl).toBe('/services/couples');
  });

  it('retains its distinct photographic hero and usable alternate text', () => {
    expect(post.image).toBe(SOURCE_IMAGE);
    expect(post.imageIsFallback).toBe(false);
    expect(post.imageAlt).toContain('אלבום תמונות');
    expect(post.imageCredit).toContain('Adobe Firefly');
  });

  it('remains grounded, avoids duplicate identity and offers relevant internal links', () => {
    const evidence = 'evidence' in post && Array.isArray(post.evidence) ? post.evidence : [];
    expect(evidence.length).toBeGreaterThanOrEqual(3);
    expect(post.content).toContain('/blog/we-language-relationships');
    expect(post.content).toContain('/blog/how-to-repair-after-couple-fight');
    expect(post.content).toContain('/services/couples');
    expect(post.content).toContain('אינה הוכחה');
  });
});
