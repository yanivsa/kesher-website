const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { ROOT, STATIC_ROUTES, isPublishable, blogRoute, wordCount, headingCount, stripHtml } = require('./content-policy.cjs');

const posts = JSON.parse(fs.readFileSync(path.join(ROOT, 'src/data/posts.json'), 'utf8'));
const published = posts.filter(isPublishable);
const postSummaries = JSON.parse(fs.readFileSync(path.join(ROOT, 'src/data/postSummaries.json'), 'utf8'));
const errors = [];
const ensureUnique = (label, values) => {
  const seen = new Set();
  for (const value of values) {
    if (seen.has(value)) errors.push(`Duplicate ${label}: ${value}`);
    seen.add(value);
  }
};

ensureUnique('post id', published.map((post) => post.id));
ensureUnique('post title', published.map((post) => post.title));
ensureUnique('post image', published.map((post) => post.image).filter(Boolean));

const seenImageShas = new Map();
for (const post of posts) {
  if (post.image) {
    const imagePath = path.join(ROOT, 'public', post.image.replace(/^\//, ''));
    if (fs.existsSync(imagePath)) {
      const fileBytes = fs.readFileSync(imagePath);
      const hash = crypto.createHash('sha256').update(fileBytes).digest('hex');
      if (seenImageShas.has(hash)) {
        errors.push(`Duplicate image content (SHA-256 hash collision ${hash.slice(0, 12)}...) between '${post.id}' and '${seenImageShas.get(hash)}'`);
      } else {
        seenImageShas.set(hash, post.id);
      }
    }
  }
}

const expectedPostSummaries = published.map(({ id, title, date, category, subcategory, excerpt, image }) => ({
  id,
  title,
  date,
  category,
  ...(subcategory ? { subcategory } : {}),
  excerpt,
  image,
}));
if (JSON.stringify(postSummaries) !== JSON.stringify(expectedPostSummaries)) {
  errors.push('Post summaries are stale or incomplete; run npm run generate after the final posts.json edit.');
}

for (let i = 0; i < published.length; i++) {
  const post = published[i];
  if (post.date > '2026-07-15' && /<h3[^>]*>\s*(סיכום|לסיכום|סיכום וצעדים הבאים|צעדים הבאים)\s*<\/h3>/.test(post.content)) errors.push('Generic final H3 found in post: ' + post.id);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(post.date)) errors.push(`Invalid date: ${post.id}`);
  if (post.image) {
    if (!post.image.startsWith('/images/')) errors.push(`Non-local image: ${post.id}`);
    if (!fs.existsSync(path.join(ROOT, 'public', post.image.replace(/^\//, '')))) errors.push(`Missing image: ${post.id}`);
    if (!post.imageAlt || post.imageAlt.trim().length < 20) errors.push(`Missing or underspecified imageAlt in post: ${post.id}`);
  }
  if (/<script|onerror=|onclick=|javascript:/i.test(post.content)) errors.push(`Unsafe HTML: ${post.id}`);
  if (wordCount(post.content) < 500 || headingCount(post.content) < 5) errors.push(`Thin content: ${post.id}`);
  if (/מוסמכת|הדרך היחידה|טראומות לא נשכחות/.test(post.content)) errors.push(`Unsupported absolute claim: ${post.id}`);

  if (post.date > '2026-07-15') {
    if (/[a-zA-Z]/.test(post.title) || /[a-zA-Z]/.test(post.excerpt) || /[a-zA-Z]/.test(stripHtml(post.content))) {
      errors.push(`Latin characters found in visible prose: ${post.id}`);
    }

    const forbiddenPhrases = [
      "גשר מעל התהום", "גשר מחדש מעל התהום", "שריר של שיח", "השריר של שיח זוגי",
      "הפרויקט המשותף הגדול הסתיים", "רעש רגשי גדול", "השקט הפיזי בבית מציף רעש רגשי גדול",
      "עמדה של יצירה משותפת", "מייצר ואקום אדיר", "הזדמנות פז אמיתית ומעשית",
      "הילדים הם הדבק החזק ביותר", "השקט לא חייב להיות אויב", "אזור הנוחות החדש",
      "הסקרנות היא המפתח", "להפסיק לנהל ולהתחיל לחיות", "תוקף רגשי",
      "המערכת תתאזן מעצמה", "הדבר הנכון הוא פשוט", "זירת התגוששות", "שדה מוקשים",
      "חקירות צולבות", "לאבד את שיווי המשקל", "לנווט את התקופה",
      "משפט תגובה קצר וחותך", "משפט קצר וחותך שמעביר את השליטה",
    ];
    const latestArticlePhrases = [
      "זה קורה כמעט לכל מי", "טבעית לחלוטין", "הצעד הראשון להתמודדות", "המלכודת הגדולה ביותר", "הקצב שלכם הוא הקצב שלכם", "אין לוח זמנים אוניברסלי", "מלאים ושלמים יותר",
      "הבנה עמוקה", "חיבור אמיתי", "לנווט את החיים", "מזמינה אתכם לעשות סדר במחשבות",
      "נובעות לרוב משילוב", "הדור הקודם גדל על מסלול חיים מאוד ברור",
      "החריגה ממנו מעוררת אצלם חרדה", "התגובה הטבעית היא", "הכלל החשוב ביותר",
    ];
    const visibleProse = `${post.title}\n${post.excerpt}\n${stripHtml(post.content)}`;
    for (const phrase of forbiddenPhrases) {
      if (visibleProse.includes(phrase)) {
        errors.push(`Forbidden formulaic AI phrase found in new article ${post.id}: "${phrase}"`);
      }
    }
    if (i === 0) {
      for (const phrase of latestArticlePhrases) {
        if (visibleProse.includes(phrase)) {
          errors.push(`Forbidden observed phrase found in latest article ${post.id}: "${phrase}"`);
        }
      }

      const STOP_WORDS = new Set(['couples', 'parenting', 'relationship', 'children', 'child', 'with', 'about', 'how', 'why', 'what', 'when', 'your', 'their']);
      const getWords = (id) => new Set(id.split('-').filter(w => w.length > 3 && !STOP_WORDS.has(w.toLowerCase())));
      const currentWords = getWords(post.id);

      for (let j = i + 1; j < Math.min(i + 31, published.length); j++) {
        const olderPost = published[j];
        const olderWords = getWords(olderPost.id);
        const intersection = [...currentWords].filter(x => olderWords.has(x));

        if (intersection.length >= 2) {
          errors.push(`Topic too similar: '${post.id}' shares specific theme keywords (${intersection.join(', ')}) with recent post '${olderPost.id}'. Please write about a substantially fresh topic.`);
          break;
        }
      }
    }
  }
}

const sitemap = fs.readFileSync(path.join(ROOT, 'public/sitemap.xml'), 'utf8');
const noindexRoutes = new Set(['/thank-you-booked', '/thank-you-contact']);
const indexableStaticRoutes = STATIC_ROUTES.filter((route) => !noindexRoutes.has(route));
for (const route of [...indexableStaticRoutes, ...published.map(blogRoute)]) {
  const url = `https://kesher.saharoni.com${route === '/' ? '' : route}`;
  if (!sitemap.includes(`<loc>${url}</loc>`)) errors.push(`Missing sitemap URL: ${url}`);
}
for (const post of posts.filter((post) => !isPublishable(post))) {
  if (sitemap.includes(`/blog/${post.id}</loc>`)) errors.push(`Thin post remains indexed: ${post.id}`);
}

const unsupportedClaims = [
  /(מטפלת|פסיכולוגית|פסיכותרפיסטית|עובדת סוציאלית|מאמנת)\s+מוסמכת/,
  /מומחית/,
  /\bGottman\b/i,
  /\bEFT\b/,
  /licensed therapist/i,
  /הסיכויים להצלחה גבוהים יותר/,
  /יעילה יותר מטיפול ישיר/,
  /המנגנון הנוירולוגי של הילד/,
];
const claimFiles = [
  'src/constants/siteConfig.ts',
  'src/pages/Home/Home.tsx',
  'src/pages/About/AboutPage.tsx',
  'src/pages/Services/Couples/CouplesCounseling.tsx',
  'src/pages/Services/Parenting/ParentingGuidance.tsx',
  'src/pages/Services/Mediation/MediationPage.tsx',
  'src/pages/Services/Gifted/GiftedParentingPage.tsx',
  'src/pages/Services/Aliyah/AliyahFamiliesPage.tsx',
  'src/pages/Services/Relocation/CouplesAliyahRelocationPage.tsx',
  'src/pages/Services/Premarital/PremaritalFirstYearPage.tsx',
  'src/pages/Services/Singles/LateSinglenessPage.tsx',
  'src/pages/Services/Singles/FindingRelationshipPage.tsx',
  'src/data/faqs.ts',
  'public/llms.txt',
];
for (const relative of claimFiles) {
  const content = fs.readFileSync(path.join(ROOT, relative), 'utf8');
  for (const pattern of unsupportedClaims) {
    if (pattern.test(content)) errors.push(`Unsupported claim in ${relative}: ${pattern}`);
  }
}

if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

console.log(`Validated ${published.length} published posts; ${posts.length - published.length} thin legacy posts remain unindexed.`);
