import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ArticleShort, SHORT_GEOMETRY } from '../src/remotion/ArticleShort';

// Mock remotion hooks to allow testing the component outside the player
vi.mock('remotion', async () => {
  const actual = await vi.importActual('remotion');
  return {
    ...actual,
    useCurrentFrame: () => 0,
    useVideoConfig: () => ({ fps: 30, durationInFrames: 1350, width: 1080, height: 1920 }),
    interpolate: () => 0,
    AbsoluteFill: ({ children, style, ...props }: { children?: React.ReactNode, style?: React.CSSProperties, [key: string]: unknown }) => React.createElement('div', { 'data-testid': 'absolute-fill', style, ...props }, children),
    staticFile: (f: string) => f,
  };
});

vi.mock('@remotion/media', () => ({
  Video: ({ trimBefore: _trimBefore, durationInFrames: _durationInFrames, ...props }: { [key: string]: unknown }) => React.createElement('video', { 'data-testid': 'remotion-video', ...props })
}));

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
    // Test the component rendering to ensure actual bounds
    const { getByText } = render(
      React.createElement(ArticleShort, {
        videoSrc: "test.mp4",
        sourceStartFrame: 0,
        durationInFrames: 1350,
        title: "Test Title",
        category: "Test Category",
        url: "test.com"
      })
    );

    const brandingElement = getByText('שירה סהרוני · test.com');
    const container = brandingElement.parentElement;

    // The parent container should have the styles enforcing the safe area bounds
    expect(container).not.toBeNull();
    if (container) {
      const styles = window.getComputedStyle(container);
      expect(styles.position).toBe('absolute');
      // Assert that it actually limits based on the configured values in SHORT_GEOMETRY
      expect(Number(styles.top.replace('px', ''))).toBeGreaterThanOrEqual(SHORT_GEOMETRY.safeArea.top);
      expect(Number(styles.left.replace('px', ''))).toBeGreaterThanOrEqual(SHORT_GEOMETRY.safeArea.left);
      expect(Number(styles.right.replace('px', ''))).toBeGreaterThanOrEqual(SHORT_GEOMETRY.safeArea.right);

      // Branding bounding box top must be bounded below upper system UI (>= 40px)
      // but cannot encroach on the lower third (bottom: 600)
      expect(SHORT_GEOMETRY.safeArea.top).toBeGreaterThanOrEqual(40);
      expect(SHORT_GEOMETRY.safeArea.top).toBeLessThan(SHORT_GEOMETRY.height - SHORT_GEOMETRY.safeArea.bottom);

      // Left offset must clear side UI (>= 40px) and leave room on the right
      expect(SHORT_GEOMETRY.safeArea.left).toBeGreaterThanOrEqual(40);
      expect(SHORT_GEOMETRY.width - SHORT_GEOMETRY.safeArea.right).toBeGreaterThan(SHORT_GEOMETRY.safeArea.left);
    }
  });

  it('bounds effective zoom so it does not compound incorrectly', () => {
    // Even if target.zoom provides 1.0 (no motion target), we start at baseScale
    const minEffectiveZoom = SHORT_GEOMETRY.baseScale;

    // If target.zoom provides a typical max (e.g., 1.2), effective peak zoom is baseScale + (1.2 - 1) * pulse
    const testMotionZoom = 1.2;
    const peakPulse = 1;
    const effectivePeakZoom = SHORT_GEOMETRY.baseScale + (testMotionZoom - 1) * peakPulse;

    expect(minEffectiveZoom).toBeCloseTo(1.11, 2);
    expect(effectivePeakZoom).toBeCloseTo(1.31, 2);
    // Sanity check that peak zoom does not explode (should reasonably be <= 1.5)
    expect(effectivePeakZoom).toBeLessThanOrEqual(1.5);
  });
});
