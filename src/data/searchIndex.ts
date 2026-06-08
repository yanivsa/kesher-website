import posts from './posts.json';
import faqs from './faqs';

export interface SearchItem {
  id: string;
  type: 'blog' | 'faq' | 'service' | 'page';
  title: string;
  body: string;
  url: string;
  category?: string;
}

const servicePages: SearchItem[] = [
  {
    id: 'service-couples',
    type: 'service',
    title: 'ייעוץ זוגי',
    body: 'ייעוץ זוגי באשדוד. תקשורת שנתקעה, אינטימיות שנעלמה, משבר אמון. הכנה לחתונה לזוגות עם הורים גרושים. ייעוץ זוגי מותאם ADHD. גישה רב-תחומית המשלבת כלים מעולם הגישור, הטיפול הזוגי והאימון.',
    url: '/services/couples',
    category: 'שירותים'
  },
  {
    id: 'service-parenting',
    type: 'service',
    title: 'הדרכת הורים',
    body: 'הדרכת הורים באשדוד. התמחות ב-ADHD. גבולות בלי מאבקים, הכנה לכיתה א לילדים עם ADHD, מוכנות רגשית, שגרת בוקר, עצמאות, קשר עם צוות חינוכי. כלים פרקטיים לניהול מצבים יומיומיים.',
    url: '/services/parenting',
    category: 'שירותים'
  },
  {
    id: 'service-mediation',
    type: 'service',
    title: 'גישור משפחתי',
    body: 'גישור משפחתי באשדוד. חיסכון בזמן, חיסכון בכסף, שליטה מלאה על ההחלטות, שמירה על טובת הילדים. הסכם גישור בתוקף משפטי. הליך בהסכמה במקום בית משפט. פתרון סכסוכי רכוש, ילדים, מזונות ומגורים.',
    url: '/services/mediation',
    category: 'שירותים'
  }
];

const staticPages: SearchItem[] = [
  {
    id: 'page-about',
    type: 'page',
    title: 'אודות שירה סהרוני',
    body: 'יועצת זוגית ומגשרת מוסמכת באשדוד בעלת ניסיון מקצועי. גישה רב-תחומית. הכשרה בייעוץ זוגי, הדרכת הורים וגישור משפחתי. מאמינה בתהליך מכבד, מעשי וממוקד.',
    url: '/about',
    category: 'דפים'
  },
  {
    id: 'page-contact',
    type: 'page',
    title: 'צור קשר / קביעת פגישה',
    body: 'קביעת פגישת היכרות ללא עלות. טלפון, WhatsApp, אימייל. אשדוד ואונליין דרך Zoom. שלחו הודעה ואחזור אליכם תוך 24 שעות.',
    url: '/contact',
    category: 'דפים'
  }
];

function buildSearchIndex(): SearchItem[] {
  const blogItems: SearchItem[] = posts.map(post => ({
    id: `blog-${post.id}`,
    type: 'blog' as const,
    title: post.title,
    body: post.excerpt,
    url: `/blog/${post.id}`,
    category: post.category
  }));

  const faqItems: SearchItem[] = faqs.map((faq, i) => ({
    id: `faq-${i}`,
    type: 'faq' as const,
    title: faq.question,
    body: faq.answer,
    url: '/faq',
    category: faq.category
  }));

  return [...blogItems, ...faqItems, ...servicePages, ...staticPages];
}

export const searchIndex = buildSearchIndex();
