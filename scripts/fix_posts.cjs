const fs = require('fs');
const path = require('path');

const postsFile = path.join(__dirname, '../src/data/posts.json');
let posts = JSON.parse(fs.readFileSync(postsFile, 'utf8'));

// Fix relocation post
const relocationPost = posts.find(p => p.id === 'relocation-crisis-couple');
if (relocationPost) {
    relocationPost.slug = 'relocation-couple-conversations-before-moving';
    relocationPost.title = '7 שיחות שחייבים לעשות לפני שאורזים: החלום האמריקאי הפך לסיוט זוגי?';
    if (!relocationPost.content.includes('/services/couples-aliyah-relocation')) {
        relocationPost.content += '\n\n<p>למידע נוסף על <a href="/services/couples-aliyah-relocation">ייעוץ זוגי בעלייה וברילוקיישן</a>, לחצו כאן.</p>';
    }
}

// Fix marriage prep post
const premaritalPost = posts.find(p => p.id === 'five-questions-before-marriage');
if (premaritalPost) {
    premaritalPost.slug = 'premarital-questions-before-wedding';
    premaritalPost.title = '12 שאלות שחייבים לשאול לפני החתונה (ולפני ששוברים את הכוס)';
    if (!premaritalPost.content.includes('/services/premarital-first-year')) {
        premaritalPost.content += '\n\n<p>למידע נוסף על <a href="/services/premarital-first-year">פגישות הכנה לנישואים</a>, לחצו כאן.</p>';
    }
}

fs.writeFileSync(postsFile, JSON.stringify(posts, null, 2), 'utf8');
console.log("Fixed posts successfully!");
