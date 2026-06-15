import { describe, it, expect } from 'vitest';
import { getImageDimensions } from '../../src/data/imageDimensions';

describe('getImageDimensions', () => {
  it('should return correct dimensions for a known image source', () => {
    const result = getImageDimensions('/images/generated/site/home-hero.jpg');
    expect(result).toEqual({ width: 1600, height: 900 });
  });

  it('should return fallback dimensions for an unknown image source', () => {
    const result = getImageDimensions('/images/unknown/path.jpg');
    expect(result).toEqual({ width: 512, height: 512 });
  });

  it('should return fallback dimensions for an empty string', () => {
    const result = getImageDimensions('');
    expect(result).toEqual({ width: 512, height: 512 });
  });
});
