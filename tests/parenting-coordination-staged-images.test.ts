import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const stagedSlugs = [
  'parenting-coordination-first-meeting-process',
  'parenting-coordination-cost-private-public',
  'parenting-coordination-domestic-violence-safety',
  'child-refuses-parenting-time-after-divorce',
] as const;

// Read actual committed JPEG headers; do not infer technical quality from extension.
const jpegDimensions = (buf: Buffer) => {
  if (buf.length < 4 || buf[0] !== 0xff || buf[1] !== 0xd8) {
    throw new Error('Missing JPEG SOI marker');
  }
  let offset = 2;
  while (offset + 4 < buf.length) {
    if (buf[offset] !== 0xff) throw new Error('Invalid JPEG marker boundary');
    while (buf[offset] === 0xff) offset += 1;
    const marker = buf[offset++];
    if (marker === 0xd9) break;
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd8)) continue;
    if (offset + 2 > buf.length) break;
    const length = buf.readUInt16BE(offset);
    if (length < 2 || offset + length > buf.length) throw new Error('Invalid JPEG segment length');
    if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker)) {
      if (length < 7) throw new Error('Invalid JPEG SOF length');
      return { width: buf.readUInt16BE(offset + 5), height: buf.readUInt16BE(offset + 3) };
    }
    offset += length;
  }
  throw new Error('No JPEG dimensions found');
};

describe('four unpublished parenting-coordination editorial images', () => {
  it('stores four distinct, realistic-size landscape JPEG files with usable pixel dimensions', () => {
    const shaSet = new Set<string>();
    for (const slug of stagedSlugs) {
      const path = resolve(process.cwd(), 'public/images/parenting-coordination/editorial-drafts', slug + '.jpg');
      const bytes = readFileSync(path);
      const { width, height } = jpegDimensions(bytes);
      expect(bytes.byteLength, slug).toBeGreaterThan(30_000);
      expect(width, slug).toBeGreaterThanOrEqual(1200);
      expect(height, slug).toBeGreaterThanOrEqual(675);
      expect(width / height, slug).toBeGreaterThan(1.7);
      expect(width / height, slug).toBeLessThan(1.85);
      shaSet.add(createHash('sha256').update(bytes).digest('hex'));
    }
    expect(shaSet.size).toBe(stagedSlugs.length);
  });

  it('keeps editorial drafts unpublished until separate professional approval', () => {
    for (const slug of stagedSlugs) {
      const draft = JSON.parse(readFileSync(resolve(process.cwd(), 'src/data/parentingCoordinationDrafts', slug + '.json'), 'utf8'));
      expect(draft.publicationState).toBe('editorial_draft_unpublished');
      expect(draft.date).toBeNull();
      expect(draft.updatedAt).toBeNull();
      expect(draft.image).toBeNull();
    }
  });
});
