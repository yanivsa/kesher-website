import { describe, it, expect } from 'vitest';
import { SHORT_GEOMETRY } from '../src/remotion/ArticleShort';

describe('ArticleShortGeometry', () => {
  it('maintains 1080x1920 resolution and 9:16 aspect ratio', () => {
    expect(SHORT_GEOMETRY.width).toBe(1080);
    expect(SHORT_GEOMETRY.height).toBe(1920);
    expect(SHORT_GEOMETRY.width / SHORT_GEOMETRY.height).toBeCloseTo(9 / 16);
  });

  it('implements approximately 90% source framing (1.11 scale)', () => {
    expect(SHORT_GEOMETRY.baseScale).toBeCloseTo(1.11, 2);
  });

  it('reserves the lower third for captions and right side for controls', () => {
    expect(SHORT_GEOMETRY.safeArea.bottom).toBeGreaterThanOrEqual(600);
    expect(SHORT_GEOMETRY.safeArea.right).toBeGreaterThanOrEqual(120);
  });

  it('places branding within the upper safe area geometry', () => {
    expect(SHORT_GEOMETRY.safeArea.top).toBeGreaterThanOrEqual(40);
    expect(SHORT_GEOMETRY.safeArea.left).toBeGreaterThanOrEqual(40);
  });
});
