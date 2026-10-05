import { describe, expect, it } from 'vitest';
import {
  canonicalRedirectTarget,
  legacyRedirectTarget,
} from '../functions/_middleware';

describe('legacy domain migration', () => {
  it('preserves the legacy homepage path', () => {
    expect(legacyRedirectTarget('https://shira.saharoni.com/')).toBe(
      'https://kesher.saharoni.com/',
    );
  });

  it('preserves current site paths and query strings', () => {
    expect(
      legacyRedirectTarget('https://shira.saharoni.com/about'),
    ).toBe('https://kesher.saharoni.com/about');

    expect(
      legacyRedirectTarget(
        'https://shira.saharoni.com/services/couples?x=1',
      ),
    ).toBe('https://kesher.saharoni.com/services/couples?x=1');

    expect(
      legacyRedirectTarget('https://shira.saharoni.com/blog?src=legacy'),
    ).toBe('https://kesher.saharoni.com/blog?src=legacy');
  });

  it('redirects legacy Blogger posts to the new blog and preserves query strings', () => {
    expect(
      legacyRedirectTarget(
        'https://shira.saharoni.com/2025/08/blog-post_75.html?m=1',
      ),
    ).toBe('https://kesher.saharoni.com/blog?m=1');
  });

  it('maps legacy static pages to their new equivalents and preserves query strings', () => {
    expect(
      legacyRedirectTarget('https://shira.saharoni.com/p/contact.html?ref=old'),
    ).toBe('https://kesher.saharoni.com/contact?ref=old');
  });

  it('does not redirect the primary domain', () => {
    expect(legacyRedirectTarget('https://kesher.saharoni.com/')).toBeNull();
  });
});

describe('canonical route redirects', () => {
  it('redirects the former beta route to the primary homepage', () => {
    expect(canonicalRedirectTarget('https://kesher.saharoni.com/b')).toBe(
      'https://kesher.saharoni.com',
    );
    expect(canonicalRedirectTarget('https://kesher.saharoni.com/b/')).toBe(
      'https://kesher.saharoni.com',
    );
  });

  it('redirects the promoted beta2 route to the primary homepage', () => {
    expect(canonicalRedirectTarget('https://kesher.saharoni.com/beta2')).toBe(
      'https://kesher.saharoni.com',
    );
    expect(canonicalRedirectTarget('https://kesher.saharoni.com/beta2/')).toBe(
      'https://kesher.saharoni.com',
    );
  });

  it('redirects legacy article and service aliases to their canonical routes', () => {
    expect(
      canonicalRedirectTarget(
        'https://kesher.saharoni.com/blog/child-starting-school-high?utm_source=old',
      ),
    ).toBe(
      'https://kesher.saharoni.com/blog/child-starting-school-high-cognition?utm_source=old',
    );

    expect(
      canonicalRedirectTarget('https://kesher.saharoni.com/services/couples/ashdod'),
    ).toBe('https://kesher.saharoni.com/couples-counseling-ashdod');

    expect(
      canonicalRedirectTarget('https://kesher.saharoni.com/services/singles-guidance/'),
    ).toBe('https://kesher.saharoni.com/services/late-singleness');
  });

  it('leaves other primary routes unchanged', () => {
    expect(canonicalRedirectTarget('https://kesher.saharoni.com/about')).toBeNull();
  });
});
