const fs = require('fs');
const path = require('path');

const llmsPath = path.join(__dirname, '../public/llms.txt');
const faqPath = path.join(__dirname, '../src/data/faqs.ts');
const postsPath = path.join(__dirname, '../src/data/posts.json');
const outputPath = path.join(__dirname, '../public/llms-full.txt');
const { isPublishable } = require('./content-policy.cjs');

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


// Add Service Pages Content
fullContent += '## עמודי שירות מפורטים (Detailed Services)\n\n';
const services = [
  { name: 'ייעוץ זוגי', path: path.join(__dirname, '../src/pages/Services/Couples/CouplesCounseling.tsx') },
  { name: 'הדרכת הורים', path: path.join(__dirname, '../src/pages/Services/Parenting/ParentingGuidance.tsx') }
];

services.forEach(service => {
  fullContent += `### ${service.name}\n\n`;
  if (fs.existsSync(service.path)) {
    const serviceContent = fs.readFileSync(service.path, 'utf8');

    // Extract text from <p>, <li>, <h3>, <h2>
    const tagsRegex = /<(p|li|h2|h3)[^>]*>(.*?)<\/\1>/gs;
    let match;
    while ((match = tagsRegex.exec(serviceContent)) !== null) {
      let text = match[2]
        .replace(/<[^>]+>/g, '') // remove inner tags like <br/>, <span>
        .trim();

      // Ignore short or irrelevant lines or React code
      if (text.length > 5 && !text.includes('className=')) {
        if (match[1] === 'h2' || match[1] === 'h3') {
           fullContent += `\n#### ${text}\n`;
        } else if (match[1] === 'li') {
           fullContent += `- ${text}\n`;
        } else {
           fullContent += `${text}\n\n`;
        }
      }
    }
  }
  fullContent += '\n';
});

// 3. Add Blog Posts
fullContent += '## מאמרים מלאים (Blog Posts)\n\n';
const posts = JSON.parse(fs.readFileSync(postsPath, 'utf8'));

posts.filter(isPublishable).forEach(post => {
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
