const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

test('post stdin mode audits one article and returns JSON', () => {
  const script = path.resolve(__dirname, '../scripts/hebrew-prose-audit.cjs');
  const post = {
    id: 'candidate-post',
    date: '2026-11-03',
    title: 'כותרת בדיקה',
    excerpt: 'תקציר קצר',
    content: '<p>חשוב לזכור משהו. חשוב לזכור עוד דבר. חשוב לזכור נקודה שלישית.</p>',
  };
  const result = spawnSync(process.execPath, [script, '--post-stdin', '--format=json'], {
    input: JSON.stringify(post),
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr);
  const parsed = JSON.parse(result.stdout);
  assert.equal(parsed.id, post.id);
  assert.equal(parsed.date, post.date);
  assert.equal(parsed.risk, 'watch');
  assert.ok(parsed.findings.some((item) => item.category === 'formulaic-phrases'));
});
