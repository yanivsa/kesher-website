import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import manualPostsOct2026 from '../src/data/manualPostsOct2026';

const slug = 'family-chores-quality-time-with-kids';
const hero = '/images/generated/blog/parenting-the-stubborn-child.jpg';

describe('manual article publication hero contract', () => {
  it('keeps the chores article eligible for exact-source publication verification', () => {
    const post = manualPostsOct2026.find((item) => item.slug === slug) as { image?: string } | undefined;

    expect(post).toBeDefined();
    expect(post?.image).toBe(hero);
    expect(existsSync(join(process.cwd(), 'public', hero.slice(1)))).toBe(true);
  });
});
