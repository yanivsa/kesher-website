const assert = require('node:assert/strict');
const test = require('node:test');
const {
  extractBlogLinks,
  validateInternalLinkPlan,
  auditInternalLinkCoverage,
} = require('../scripts/internal-link-policy.cjs');

test('extractBlogLinks normalizes relative and same-domain blog links', () => {
  const html = [
    '<a href="/blog/alpha">Alpha</a>',
    "<a href='/blog/beta'>Beta</a>",
    '<a href="https://kesher.saharoni.com/blog/gamma?utm=1#x">Gamma</a>',
    '<a href="https://example.com/blog/external">External</a>',
    '<a href="/services/couples">Service</a>',
  ].join(' ');
  assert.deepEqual(extractBlogLinks(html), ['/blog/alpha', '/blog/beta', '/blog/gamma']);
});

test('validateInternalLinkPlan rejects missing sources, missing targets, self-links and duplicates', () => {
  const posts = [{ id: 'alpha' }, { id: 'beta' }];
  const plan = [
    { source: 'missing', targets: ['beta'] },
    { source: 'alpha', targets: ['alpha', 'missing-target', 'beta', 'beta'] },
  ];
  const errors = validateInternalLinkPlan(posts, plan);
  assert.ok(errors.some((x) => x.includes('missing source')));
  assert.ok(errors.some((x) => x.includes('self-link')));
  assert.ok(errors.some((x) => x.includes('missing target')));
  assert.ok(errors.some((x) => x.includes('duplicate target')));
});

test('auditInternalLinkCoverage reports present and missing planned links without treating missing as invalid', () => {
  const posts = [
    { id: 'alpha', content: '<p>See <a href="/blog/beta">beta</a></p>' },
    { id: 'beta', content: '<p>Beta</p>' },
    { id: 'gamma', content: '<p>Gamma</p>' },
  ];
  const plan = [{ source: 'alpha', targets: ['beta', 'gamma'] }];
  const audit = auditInternalLinkCoverage(posts, plan);
  assert.equal(audit.planned, 2);
  assert.equal(audit.present, 1);
  assert.equal(audit.missing, 1);
  assert.deepEqual(audit.rows, [
    { source: 'alpha', target: 'beta', present: true },
    { source: 'alpha', target: 'gamma', present: false },
  ]);
});
