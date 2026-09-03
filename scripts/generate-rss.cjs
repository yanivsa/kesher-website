const fs = require('fs');
const path = require('path');
const { ROOT, isPublishable } = require('./content-policy.cjs');

const sourcePath = path.join(ROOT, 'src', 'data', 'posts.json');
const outputPath = path.join(ROOT, 'public', 'rss.xml');

const escapeXml = (unsafe) => {
  if (!unsafe) return '';
  return unsafe.replace(/[<>&'"]/g, (c) => {
    switch (c) {
      case '<': return '&lt;';
      case '>': return '&gt;';
      case '&': return '&amp;';
      case '\'': return '&apos;';
      case '"': return '&quot;';
      default: return c;
    }
  });
};

const posts = JSON.parse(fs.readFileSync(sourcePath, 'utf8'));
const published = posts.filter(isPublishable);

// Sort by date descending
published.sort((a, b) => (b.date > a.date ? 1 : -1));

const buildRss = (items) => {
  const latestDate = items[0]?.date ? new Date(items[0].date).toUTCString() : new Date().toUTCString();
  
  const itemXml = items.map((post) => {
    const postDate = new Date(post.date).toUTCString();
    const postUrl = `https://kesher.saharoni.com/blog/${post.id}`;
    return `    <item>
      <title>${escapeXml(post.title)}</title>
      <link>${postUrl}</link>
      <guid isPermaLink="true">${postUrl}</guid>
      <pubDate>${postDate}</pubDate>
      <description>${escapeXml(post.excerpt)}</description>
      <category>${escapeXml(post.category)}</category>
      <author>shira@saharoni.com (Shira Saharoni)</author>
    </item>`;
  }).join('\n');

  return `<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>קשר סהרוני | מאמרים מקצועיים בזוגיות, הורות וגישור</title>
    <link>https://kesher.saharoni.com/blog</link>
    <description>מאמרים מקצועיים, תובנות וכלים מעשיים בנושאי ייעוץ זוגי, הדרכת הורים וגישור משפחתי מאת שירה סהרוני.</description>
    <language>he-IL</language>
    <lastBuildDate>${latestDate}</lastBuildDate>
    <managingEditor>shira@saharoni.com (Shira Saharoni)</managingEditor>
    <webMaster>shira@saharoni.com (Shira Saharoni)</webMaster>
    <atom:link href="https://kesher.saharoni.com/rss.xml" rel="self" type="application/rss+xml" />
${itemXml}
  </channel>
</rss>
`;
};

const rssContent = buildRss(published);
fs.writeFileSync(outputPath, rssContent, 'utf8');
console.log(`Generated RSS feed with ${published.length} items at ${outputPath}`);
