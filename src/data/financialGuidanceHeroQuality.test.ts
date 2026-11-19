/**
 * Reviewed finance heroes and forward-only editorial image policy.
 * Static manual pixel assessments are pinned to git-blob hashes, so changing an
 * approved picture cannot silently bypass a visual/editorial review.
 * The daily canonical article pipeline independently uses Gemini pixel verification.
 */
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import posts from './financialGuidancePosts.json';
import approvals from './financialGuidanceHeroApprovals.json';
import summaries from './postSummaries.json';

const CUTOFF = '2026-11-17';

function dimensionsOfJpeg(data: Buffer): { width: number; height: number } {
  if (data.length < 4096 || data[0] !== 0xff || data[1] !== 0xd8) {
    throw new Error('Hero must be a valid nonempty JPEG');
  }
  let offset = 2;
  while (offset + 4 < data.length) {
    if (data[offset] !== 0xff) throw new Error('Invalid JPEG marker boundary');
    while (data[offset] === 0xff) offset++;
    const marker = data[offset++];
    if (marker === 0xd9 || marker === 0xda) break;
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue;
    if (offset + 2 > data.length) break;
    const size = data.readUInt16BE(offset);
    offset += 2;
    if (size < 2 || offset + size - 2 > data.length) throw new Error('Invalid JPEG segment length');
    if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker)) {
      return { height: data.readUInt16BE(offset + 1), width: data.readUInt16BE(offset + 3) };
    }
    offset += size - 2;
  }
  throw new Error('Cannot decode JPEG frame dimensions');
}

describe('financial guidance hero editorial quality approval', () => {
  it('requires exact 17 reviewed financial article scenes, no unreviewed additions', () => {
    expect(posts).toHaveLength(17);
    expect(approvals).toHaveLength(17);
    expect(posts.map((post) => post.id).sort()).toEqual(approvals.map((entry) => entry.id).sort());
    expect(new Set(posts.map((post) => post.id)).size).toBe(17);
  });

  it('prevents abstract and SVG placeholders on every newly published summary', () => {
    const recent = summaries.filter((post) => post.date >= CUTOFF);
    expect(recent.length).toBeGreaterThanOrEqual(17);
    for (const post of recent) {
      expect(post.image, post.id).toMatch(/^\/images\/[^?#]+\.(?:jpe?g|png|webp)$/i);
    }
  });

  it.each(approvals)('$id has unique full-size photographic JPEG with reviewed topic-specific alt and provenance', (approval) => {
    const post = posts.find((item) => item.id === approval.id);
    const summary = summaries.find((item) => item.id === approval.id);
    expect(post).toBeDefined();
    expect(summary?.image).toBe(approval.image);
    expect(post?.image).toBe(approval.image);
    expect(post?.imageAlt).toBe(approval.imageAlt);
    expect(post?.imageProvider).toBe(approval.imageProvider);
    expect(approval.reviewType).toBe('manual-pixel-scene-relevance');
    expect(approval.reviewedOn).toMatch(/^20\d{2}-\d{2}-\d{2}$/);
    expect(approval.imageAlt).toMatch(/[\u0590-\u05FF]/);
    expect(approval.imageAlt.length).toBeGreaterThanOrEqual(35);
    expect(approval.image).toMatch(/^\/images\/financial-guidance\/articles\/[a-z0-9-]+\.jpg$/);
    const bytes = readFileSync(resolve(process.cwd(), 'public', approval.image.slice(1)));
    expect(bytes.length).toBeGreaterThan(40_000);
    const { width, height } = dimensionsOfJpeg(bytes);
    expect(width).toBeGreaterThanOrEqual(1200);
    expect(height).toBeGreaterThanOrEqual(675);
    expect(width / height).toBeGreaterThan(1.2);
    expect(width / height).toBeLessThan(2.2);
    const gitBlobSha = createHash('sha1').update(`blob ${bytes.length}\0`).update(bytes).digest('hex');
    expect(gitBlobSha).toBe(approval.gitBlobSha);
  });

  it('never reuses hero image pixels across finance articles', () => {
    expect(new Set(approvals.map((entry) => entry.image)).size).toBe(17);
    expect(new Set(approvals.map((entry) => entry.gitBlobSha)).size).toBe(17);
  });
});
