import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const {
  extractBlogLinks,
  validateInternalLinkPlan,
  auditInternalLinkCoverage,
} = require('../scripts/internal-link-policy.cjs');

describe('internal-link policy', () => {
  it('normalizes relative and same-domain blog links', () => {
    const html = [
      '<a href="/blog/alpha">Alpha</a>',
      "<a href='/blog/beta'>Beta</a>",
      '<a href="https://kesher.saharoni.com/blog/gamma?utm=1#x">Gamma</a>',
      '<a href="https://example.com/blog/external">External</a>',
      '<a href="/services/couples">Service</a>',
    ].join(' ');

    expect(extractBlogLinks(html)).toEqual(['/blog/alpha', '/blog/beta', '/blog/gamma']);
  });

  it('rejects missing sources, missing targets, self-links and duplicates', () => {
    const posts = [{ id: 'alpha' }, { id: 'beta' }];
    const plan = [
      { source: 'missing', targets: ['beta'] },
      { source: 'alpha', targets: ['alpha', 'missing-target', 'beta', 'beta'] },
    ];

    const errors = validateInternalLinkPlan(posts, plan);

    expect(errors.some((value: string) => value.includes('missing source'))).toBe(true);
    expect(errors.some((value: string) => value.includes('self-link'))).toBe(true);
    expect(errors.some((value: string) => value.includes('missing target'))).toBe(true);
    expect(errors.some((value: string) => value.includes('duplicate target'))).toBe(true);
  });

  it('reports present and missing planned links without treating missing coverage as invalid', () => {
    const posts = [
      { id: 'alpha', content: '<p>See <a href="/blog/beta">beta</a></p>' },
      { id: 'beta', content: '<p>Beta</p>' },
      { id: 'gamma', content: '<p>Gamma</p>' },
    ];
    const plan = [{ source: 'alpha', targets: ['beta', 'gamma'] }];

    expect(auditInternalLinkCoverage(posts, plan)).toEqual({
      planned: 2,
      present: 1,
      missing: 1,
      rows: [
        { source: 'alpha', target: 'beta', present: true },
        { source: 'alpha', target: 'gamma', present: false },
      ],
    });
  });
});
