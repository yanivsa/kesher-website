const fs = require('fs');
const path = require('path');
const { ROOT, isPublishable } = require('./content-policy.cjs');
const { loadPosts } = require('./load-posts.cjs');

const outputPath = path.join(ROOT, 'src', 'data', 'postSummaries.json');
const posts = loadPosts();

const summaries = posts
  .filter(isPublishable)
  .sort((a, b) => (b.date > a.date ? 1 : b.date < a.date ? -1 : 0))
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
