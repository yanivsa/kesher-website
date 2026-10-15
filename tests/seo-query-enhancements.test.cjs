const assert = require('node:assert/strict');
const { loadPosts } = require('../scripts/load-posts.cjs');
const { isPublishable } = require('../scripts/content-policy.cjs');

const posts = loadPosts();
const byId = (id) => posts.find((post) => post.id === id);

const gifted = byId('how-to-identify-a-gifted-child-parents-guide');
assert.ok(gifted, 'gifted child article must exist');
assert.match(gifted.title, /^מה זה ילד מחונן\?/u, 'gifted article title should target the exact GSC query');
assert.match(gifted.content, /מה זה ילד מחונן\?/u, 'gifted article body should answer the exact query');
assert.match(gifted.content, /איך מוגדרת מחוננות בישראל/u, 'gifted article should explain the Israeli definition');
assert.equal(gifted.updatedAt, '2026-10-15');

const sleep = byId('sleep-needs-10-year-old');
assert.ok(sleep, 'sleep article must exist');
assert.match(sleep.content, /ילדה בת 10 לא נרדמת/u, 'sleep article should address the exact GSC query');
assert.match(sleep.content, /מתי כדאי לפנות לרופא/u, 'sleep article should include a medical escalation boundary');
assert.equal(sleep.updatedAt, '2026-10-15');

const dating = byId('dating-transition-to-relationship-boundaries');
assert.ok(dating, 'dating article must exist');
assert.match(dating.content, /האם כדאי לא להראות התלהבות בתחילת קשר\?/u, 'dating article should address the exact GSC query');
assert.equal(dating.updatedAt, '2026-10-15');

const relocation = byId('parent-guidance-relocation');
assert.ok(relocation, 'relocation parent-guidance article must exist');
assert.match(relocation.title, /^הדרכת הורים לקראת רילוקיישן/u, 'relocation title should target the exact GSC query');
assert.match(relocation.content, /מתי לספר לילדים/u, 'relocation article should cover timing the conversation');
assert.match(relocation.content, /בית ספר חדש/u, 'relocation article should cover school transition');
assert.ok(isPublishable(relocation), 'relocation article must meet the site publishability gate');

const ids = posts.map((post) => post.id);
assert.equal(ids.length, new Set(ids).size, 'SEO enhancements must not introduce duplicate post ids');

console.log('SEO query enhancement checks passed');
