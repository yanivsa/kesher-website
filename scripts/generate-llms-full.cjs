const fs = require('fs');
const path = require('path');

const llmsPath = path.join(__dirname, '../public/llms.txt');
const faqPath = path.join(__dirname, '../src/pages/FAQ/FAQ.tsx');
const postsPath = path.join(__dirname, '../src/data/posts.json');
const outputPath = path.join(__dirname, '../public/llms-full.txt');

// 1. Read llms.txt
let fullContent = fs.readFileSync(llmsPath, 'utf8');

// 2. Add FAQs
fullContent += '\n\n## שאלות ותשובות מפורטות (FAQ)\n\n';
const faqContent = fs.readFileSync(faqPath, 'utf8');
const faqRegex = /{\s*question:\s*"([^"]+)",\s*answer:\s*"([^"]+)",\s*category:\s*"([^"]+)"\s*}/g;

let match;
while ((match = faqRegex.exec(faqContent)) !== null) {
  const question = match[1];
  const answer = match[2];
  fullContent += `### ${question}\n${answer}\n\n`;
}

// 3. Add Blog Posts
fullContent += '## מאמרים מלאים (Blog Posts)\n\n';
const posts = JSON.parse(fs.readFileSync(postsPath, 'utf8'));

posts.forEach(post => {
  fullContent += `### ${post.title}\n`;
  fullContent += `תאריך: ${post.date} | קטגוריה: ${post.category}\n\n`;

  // Clean HTML from content for the llms text file
  const cleanContent = post.content
    .replace(/<h3[^>]*>/g, '\n#### ')
    .replace(/<\/h3>/g, '\n')
    .replace(/<p[^>]*>/g, '')
    .replace(/<\/p>/g, '\n\n')
    .replace(/<ul[^>]*>/g, '')
    .replace(/<\/ul>/g, '\n')
    .replace(/<li[^>]*>/g, '- ')
    .replace(/<\/li>/g, '\n')
    .replace(/<strong[^>]*>/g, '**')
    .replace(/<\/strong>/g, '**')
    .replace(/<em[^>]*>/g, '*')
    .replace(/<\/em>/g, '*')
    .replace(/<[^>]+>/g, '') // Remove remaining tags
    .trim();

  fullContent += cleanContent + '\n\n';
});

fs.writeFileSync(outputPath, fullContent, 'utf8');
console.log('Successfully generated public/llms-full.txt');
