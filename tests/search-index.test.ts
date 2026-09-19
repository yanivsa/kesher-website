import { describe, expect, it } from 'vitest';
import { searchIndex } from '../src/data/searchIndex';

describe('searchIndex structure', () => {
  it('contains expected content categories', () => {
    const types = new Set(searchIndex.map(item => item.type));
    expect(types.has('blog')).toBe(true);
    expect(types.has('faq')).toBe(true);
    expect(types.has('service')).toBe(true);
    expect(types.has('page')).toBe(true);
  });

  it('contains correctly formatted URLs', () => {
    const hasInvalidUrl = searchIndex.some(item => !item.url.startsWith('/'));
    expect(hasInvalidUrl).toBe(false);
  });

  it('has stable composition with expected service pages', () => {
    const retiredCouplesService = searchIndex.find(item => item.url === '/services/couples');
    expect(retiredCouplesService).toBeUndefined();

    const ashdodService = searchIndex.find(item => item.id === 'service-couples-ashdod');
    expect(ashdodService).toBeDefined();
    expect(ashdodService?.url).toBe('/couples-counseling-ashdod');
    expect(ashdodService?.type).toBe('service');
    expect(ashdodService?.title).toContain('ייעוץ זוגי באשדוד');
    expect(ashdodService?.category).toBe('שירותים');
    expect(ashdodService?.body).toContain('משבר אמון');
  });
});
