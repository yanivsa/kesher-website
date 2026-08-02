import { describe, expect, it } from 'vitest';
import {
  canonicalRedirectTarget,
  legacyRedirectTarget,
} from '../functions/_middleware';

describe('legacy domain migration', () => {
  it('redirects the legacy homepage to the primary homepage', () => {
    expect(legacyRedirectTarget('https://shira.saharoni.com/')).toBe(
      'https://kesher.saharoni.com/',
    );
  });

  it('redirects legacy Blogger posts to the new blog', () => {
    expect(
      legacyRedirectTarget(
        'https://shira.saharoni.com/2025/08/blog-post_75.html?m=1',
      ),
    ).toBe('https://kesher.saharoni.com/blog');
  });

  it('maps legacy static pages to their new equivalents', () => {
    expect(
      legacyRedirectTarget('https://shira.saharoni.com/p/contact.html?ref=old'),
    ).toBe('https://kesher.saharoni.com/contact');
  });

  it('does not redirect the primary domain', () => {
    expect(legacyRedirectTarget('https://kesher.saharoni.com/')).toBeNull();
  });
});

describe('canonical route redirects', () => {
  it('allows the beta route on the primary domain', () => {
    expect(canonicalRedirectTarget('https://kesher.saharoni.com/b')).toBeNull();
    expect(canonicalRedirectTarget('https://kesher.saharoni.com/b/')).toBeNull();
  });

  it('leaves other primary routes unchanged', () => {
    expect(canonicalRedirectTarget('https://kesher.saharoni.com/about')).toBeNull();
  });
});
