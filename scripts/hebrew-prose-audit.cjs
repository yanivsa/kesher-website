#!/usr/bin/env node
'use strict';

const path = require('node:path');

const FORMULAIC_PHRASES = [
  'חשוב לזכור',
  'חשוב להבין',
  'כדאי לזכור',
  'הבשורה הטובה היא',
  'המפתח הוא',
  'הצעד הראשון הוא',
  'בסופו של דבר',
  'במילים אחרות',
  'בואו נבין',
  'בואו נצלול',
  'בואו נפרק',
];

const HYPE_PHRASES = [
  'משנה חיים',
  'פתרון קסם',
  'מהפכני',
  'עוצמתי',
  'עמוק ומשמעותי',
  'חיבור אמיתי',
  'דיוק מרבי',
  'תוצאה מדהימה',
  'הזדמנות פז',
  'הכלל החשוב ביותר',
  'המלכודת הגדולה ביותר',
];

const STARTER_STOPWORDS = new Set([
  'זה', 'זו', 'זאת', 'הוא', 'היא', 'הם', 'הן', 'יש', 'אין', 'גם', 'אם', 'כי', 'אבל', 'או', 'ו',
  'כאשר', 'כש', 'לכן', 'כך', 'אז', 'מה', 'מי', 'איך', 'למה', 'אחרי', 'לפני', 'עם', 'בלי',
]);

function decodeEntities(text) {
  return String(text || '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&amp;/gi, '&')
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec) => String.fromCodePoint(parseInt(dec, 10)));
}

function stripHtml(html) {
  return decodeEntities(String(html || ''))
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<!--([\s\S]*?)-->/g, ' ')
    .replace(/<[^>]+>/g, ' ');
}

function normalizeText(text) {
  return stripHtml(text)
    .replace(/[“”„״]/g, '"')
    .replace(/[‘’׳]/g, "'")
    .replace(/\u00a0/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function splitSentences(text) {
  return normalizeText(text)
    .split(/(?<=[.!?])\s+|\s*[\n\r]+\s*/)
    .map((s) => s.trim())
    .filter((s) => s.length >= 8);
}

function countWords(text) {
  const normalized = normalizeText(text);
  return normalized ? normalized.split(/\s+/).filter(Boolean).length : 0;
}

function countPhrase(text, phrase) {
  const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return (text.match(new RegExp(escaped, 'g')) || []).length;
}

function starterKey(sentence) {
  const words = sentence
    .replace(/^["'([\{\s]+/, '')
    .split(/\s+/)
    .map((w) => w.replace(/^[^\u0590-\u05FF]+|[^\u0590-\u05FF]+$/g, ''))
    .filter(Boolean);
  if (!words.length) return '';
  if (STARTER_STOPWORDS.has(words[0]) && words[1]) return `${words[0]} ${words[1]}`;
  return words[0];
}

function finding(category, count, message, examples = []) {
  return { category, count, message, examples: examples.slice(0, 3) };
}

function auditText(input) {
  const text = normalizeText(input);
  const words = countWords(text);
  const sentences = splitSentences(text);
  const findings = [];

  const formulaCounts = FORMULAIC_PHRASES
    .map((phrase) => [phrase, countPhrase(text, phrase)])
    .filter(([, count]) => count > 0);
  const formulaTotal = formulaCounts.reduce((sum, [, count]) => sum + count, 0);
  const repeatedFormula = formulaCounts.filter(([, count]) => count >= 2);
  if (repeatedFormula.length || formulaTotal >= 4) {
    findings.push(finding(
      'formulaic-phrases',
      formulaTotal,
      'Repeated stock transition or advice phrases make the prose feel templated.',
      formulaCounts.map(([phrase, count]) => `${phrase} ×${count}`),
    ));
  }

  const contrastMatches = text.match(/לא רק[^.!?]{0,90}?(?:אלא גם|כי אם גם)/g) || [];
  if (contrastMatches.length >= 2) {
    findings.push(finding(
      'contrast-templates',
      contrastMatches.length,
      'The “not only … but also …” construction repeats enough to create a mechanical cadence.',
      contrastMatches,
    ));
  }

  const hypeCounts = HYPE_PHRASES
    .map((phrase) => [phrase, countPhrase(text, phrase)])
    .filter(([, count]) => count > 0);
  const hypeTotal = hypeCounts.reduce((sum, [, count]) => sum + count, 0);
  if (hypeTotal >= 3) {
    findings.push(finding(
      'inflated-language',
      hypeTotal,
      'Several promotional or inflated phrases appear in the same text.',
      hypeCounts.map(([phrase, count]) => `${phrase} ×${count}`),
    ));
  }

  const emDashes = (text.match(/—/g) || []).length;
  const semicolons = (text.match(/;/g) || []).length;
  const dashDensity = words ? (emDashes * 1000) / words : 0;
  const semicolonDensity = words ? (semicolons * 1000) / words : 0;
  if (emDashes >= 5 && (words < 400 || dashDensity >= 8)) {
    findings.push(finding(
      'punctuation-cadence',
      emDashes,
      'Em-dash density is high enough to sound like a repeated stylistic tic.',
      [`${emDashes} em dashes`, `${dashDensity.toFixed(1)} per 1,000 words`],
    ));
  } else if (semicolons >= 5 && semicolonDensity >= 8) {
    findings.push(finding(
      'punctuation-cadence',
      semicolons,
      'Semicolon density is high enough to deserve an editorial pass.',
      [`${semicolons} semicolons`, `${semicolonDensity.toFixed(1)} per 1,000 words`],
    ));
  }

  if (sentences.length >= 4) {
    const counts = new Map();
    for (const sentence of sentences) {
      const key = starterKey(sentence);
      if (!key) continue;
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    const repeated = [...counts.entries()]
      .filter(([, count]) => count >= 4 && count / sentences.length >= 0.25)
      .sort((a, b) => b[1] - a[1]);
    if (repeated.length) {
      findings.push(finding(
        'repetitive-starters',
        repeated[0][1],
        'Many sentences begin the same way, which can create generated-sounding rhythm.',
        repeated.map(([starter, count]) => `${starter} ×${count}`),
      ));
    }
  }

  const rhetoricalQuestions = (text.match(/\?/g) || []).length;
  const qDensity = words ? (rhetoricalQuestions * 1000) / words : 0;
  if (rhetoricalQuestions >= 6 && qDensity >= 10) {
    findings.push(finding(
      'question-cadence',
      rhetoricalQuestions,
      'Question density is unusually high and may indicate a repetitive hook pattern.',
      [`${rhetoricalQuestions} question marks`, `${qDensity.toFixed(1)} per 1,000 words`],
    ));
  }

  const riskPoints = findings.length;
  const risk = riskPoints === 0 ? 'low' : riskPoints === 1 ? 'watch' : riskPoints <= 3 ? 'medium' : 'high';
  return { risk, riskPoints, wordCount: words, sentenceCount: sentences.length, findings };
}

function auditPosts(posts, options = {}) {
  const sample = Math.max(1, Number(options.sample || 30));
  const publishable = typeof options.isPublishable === 'function' ? options.isPublishable : () => true;
  const selected = posts
    .filter((post) => post && publishable(post))
    .slice()
    .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')) || String(a.id || '').localeCompare(String(b.id || '')))
    .slice(0, sample);

  const articles = selected.map((post) => {
    const combined = `${post.title || ''}\n${post.excerpt || ''}\n${post.content || ''}`;
    return {
      id: post.id,
      date: post.date || '',
      title: post.title || '',
      ...auditText(combined),
    };
  });

  const riskCounts = { low: 0, watch: 0, medium: 0, high: 0 };
  const categoryCounts = {};
  for (const article of articles) {
    riskCounts[article.risk] += 1;
    for (const item of article.findings) {
      categoryCounts[item.category] = (categoryCounts[item.category] || 0) + 1;
    }
  }

  return {
    generatedAt: new Date().toISOString(),
    sampleRequested: sample,
    sampleAudited: articles.length,
    riskCounts,
    categoryCounts,
    articles,
  };
}

function formatMarkdownReport(report) {
  const lines = [
    '# Hebrew prose audit',
    '',
    `Audited ${report.sampleAudited} recent publishable articles. This is a report-only heuristic; it does not prove human authorship and does not block publication.`,
    '',
    `Risk counts: low ${report.riskCounts.low}, watch ${report.riskCounts.watch}, medium ${report.riskCounts.medium}, high ${report.riskCounts.high}.`,
    '',
    '## Aggregate findings',
    '',
  ];

  const categories = Object.entries(report.categoryCounts).sort((a, b) => b[1] - a[1]);
  if (!categories.length) lines.push('No heuristic findings in this sample.');
  else for (const [category, count] of categories) lines.push(`- ${category}: ${count} article(s)`);

  lines.push('', '## Articles', '', '| id | date | risk | findings |', '|---|---|---:|---|');
  for (const article of report.articles) {
    const categoriesText = article.findings.map((item) => item.category).join(', ') || '—';
    lines.push(`| ${article.id} | ${article.date} | ${article.risk} | ${categoriesText} |`);
  }
  return `${lines.join('\n')}\n`;
}

function parseArgs(argv) {
  const options = { sample: 30, format: 'markdown', strict: false };
  for (const arg of argv) {
    if (arg.startsWith('--sample=')) options.sample = Number(arg.split('=')[1]);
    else if (arg === '--json' || arg === '--format=json') options.format = 'json';
    else if (arg === '--markdown' || arg === '--format=markdown') options.format = 'markdown';
    else if (arg === '--strict') options.strict = true;
  }
  if (!Number.isFinite(options.sample) || options.sample < 1) throw new Error('--sample must be a positive number');
  return options;
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  const root = path.resolve(__dirname, '..');
  const { loadPosts } = require(path.join(root, 'scripts', 'load-posts.cjs'));
  const { isPublishable } = require(path.join(root, 'scripts', 'content-policy.cjs'));
  const report = auditPosts(loadPosts(), { sample: options.sample, isPublishable });
  process.stdout.write(options.format === 'json' ? `${JSON.stringify(report, null, 2)}\n` : formatMarkdownReport(report));
  if (options.strict && report.riskCounts.high > 0) process.exitCode = 1;
}

if (require.main === module) main();

module.exports = {
  auditText,
  auditPosts,
  formatMarkdownReport,
  normalizeText,
  splitSentences,
};
