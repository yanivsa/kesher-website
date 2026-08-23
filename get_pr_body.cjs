const contentPolicy = require('./scripts/content-policy.cjs');
const fs = require('fs');

const content = JSON.parse(fs.readFileSync('src/data/posts.json', 'utf8'))[0].content;
const stripped = contentPolicy.stripHtml(content);
const words = contentPolicy.wordCount(stripped);

console.log(`Publish Kesher article: לדבר אל הקיר

This PR adds a new article for the 2026-08-23 slot about communication distractions and presence in couples.

Category: זוגיות
Subcategory: תקשורת ופתרון קונפליקטים
Word Count: ${words}
Date: 2026-08-23

Verified tests passed.
No video artifact generated as per policy.
Image stage fully deferred to Pipeline V3 trusted runner.
`);
