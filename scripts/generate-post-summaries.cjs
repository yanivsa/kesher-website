const fs = require('fs');
const path = require('path');
const { ROOT, isPublishable } = require('./content-policy.cjs');

const sourcePath = path.join(ROOT, 'src', 'data', 'posts.json');
const outputPath = path.join(ROOT, 'src', 'data', 'postSummaries.json');
const posts = JSON.parse(fs.readFileSync(sourcePath, 'utf8'));

const summaries = posts
  .filter(isPublishable)
  .map(({ id, title, date, category, subcategory, excerpt, image }) => ({
    id,
    title,
    date,
    category,
    ...(subcategory ? { subcategory } : {}),
    excerpt,
    image,
  }));

fs.writeFileSync(outputPath, `${JSON.stringify(summaries, null, 2)}\n`);
console.log(`Generated ${summaries.length} lightweight post summaries.`);
