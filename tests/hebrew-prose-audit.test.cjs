const test = require('node:test');
const assert = require('node:assert/strict');
const { auditText, auditPosts, formatMarkdownReport } = require('../scripts/hebrew-prose-audit.cjs');

const natural = `
כשילד מתנגד לבקשה, כדאי קודם לבדוק מה בדיוק קורה באותו רגע. לפעמים הוא עייף, לפעמים הוא שקוע במשחק, ולפעמים הוא פשוט רוצה להשפיע על מה שקורה בבית.
אפשר להציב גבול קצר וברור, ואז לתת מקום לרגש בלי לפתוח את ההחלטה מחדש. אם הוויכוח חוזר בכל ערב, שווה לבדוק האם הכלל ברור והאם שני ההורים מגיבים אליו באופן דומה.
`;

test('natural Hebrew prose stays low risk', () => {
  const result = auditText(natural);
  assert.equal(result.risk, 'low');
  assert.equal(result.findings.length, 0);
});

test('repeated formulaic phrases are reported', () => {
  const text = [
    'חשוב לזכור שהשיחה אינה תחרות.',
    'חשוב לזכור שגם לילד יש נקודת מבט.',
    'חשוב לזכור שהגבול צריך להישאר ברור.',
    'חשוב לזכור שלא צריך להסביר שוב ושוב.',
  ].join(' ');
  const result = auditText(text);
  assert.ok(result.findings.some((f) => f.category === 'formulaic-phrases'));
});

test('repeated sentence starters are reported', () => {
  const text = [
    'אפשר להתחיל במשפט קצר.',
    'אפשר לתת בחירה מצומצמת.',
    'אפשר להישאר ליד הילד.',
    'אפשר לחזור על הגבול פעם אחת.',
    'אחר כך ממשיכים בשגרה.',
    'בערב בודקים מה עבד.',
  ].join(' ');
  const result = auditText(text);
  assert.ok(result.findings.some((f) => f.category === 'repetitive-starters'));
});

test('repeated not-only-but-also constructions are reported', () => {
  const text = 'זה לא רק עניין של גבולות, אלא גם של קשר. זה לא רק ויכוח, אלא גם ניסיון להשפיע. זה לא רק קושי רגעי, אלא גם דפוס שחוזר.';
  const result = auditText(text);
  assert.ok(result.findings.some((f) => f.category === 'contrast-templates'));
});

test('dense em dashes are reported', () => {
  const text = 'הורה אומר משהו — הילד מגיב — ההורה מסביר — הילד מתווכח — ושוב חוזרים להתחלה — בלי לעצור.';
  const result = auditText(text);
  assert.ok(result.findings.some((f) => f.category === 'punctuation-cadence'));
});

test('question-heavy prose is advisory only and does not raise risk', () => {
  const text = 'מה עושים עכשיו? למה זה קורה? איך מגיבים? מתי עוצרים? מי צריך לדבר? האם לחכות? מה אפשר לנסות?';
  const result = auditText(text);
  assert.equal(result.risk, 'low');
  assert.ok(result.advisories.some((f) => f.category === 'question-cadence'));
  assert.ok(!result.findings.some((f) => f.category === 'question-cadence'));
});

test('auditPosts sorts by date and caps the sample', () => {
  const posts = Array.from({ length: 35 }, (_, i) => ({
    id: `post-${i}`,
    title: `כותרת ${i}`,
    excerpt: 'תקציר שימושי',
    content: '<p>טקסט טבעי שמסביר נקודה אחת בצורה ישירה.</p>',
    date: `2026-10-${String((i % 28) + 1).padStart(2, '0')}`,
  }));
  const report = auditPosts(posts, { sample: 30, isPublishable: () => true });
  assert.equal(report.articles.length, 30);
  assert.ok(report.articles[0].date >= report.articles[29].date);
});

test('markdown report includes aggregate counts and article rows', () => {
  const report = auditPosts([
    { id: 'a', title: 'א', excerpt: '', content: '<p>טקסט טבעי וקצר.</p>', date: '2026-10-02' },
    { id: 'b', title: 'ב', excerpt: '', content: '<p>חשוב לזכור. חשוב לזכור. חשוב לזכור. חשוב לזכור.</p>', date: '2026-10-01' },
  ], { sample: 2, isPublishable: () => true });
  const markdown = formatMarkdownReport(report);
  assert.match(markdown, /Hebrew prose audit/);
  assert.match(markdown, /\| b \|/);
  assert.match(markdown, /formulaic-phrases/);
});
