import posts from './postSummaries.json';
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
    body: 'ייעוץ זוגי באשדוד. תקשורת שנתקעה, אינטימיות שנעלמה, משבר אמון. הכנה לחתונה וזוגיות עם ADHD. גישה מעשית ורגישה לחיזוק הקשר.',
    url: '/services/couples',
    category: 'שירותים'
  },
  {
    id: 'service-parenting',
    type: 'service',
    title: 'הדרכת הורים',
    body: 'הדרכת הורים באשדוד ובאונליין. ילדים מחוננים, ADHD, גבולות בלי מאבקים, הכנה לכיתה א, תפקודים ניהוליים, מוכנות רגשית, שגרת בוקר, עצמאות וקשר עם הצוות החינוכי.',
    url: '/services/parenting',
    category: 'שירותים'
  },
  {
    id: 'service-mediation',
    type: 'service',
    title: 'גישור',
    body: 'גישור באשדוד ובאונליין לבני זוג, משפחות, הורים, שכנים, עובדים ושותפים. בירור צרכים, הפחתת מתחים ובניית הסכמות מעשיות.',
    url: '/services/mediation',
    category: 'שירותים'
  },
  {
    id: 'service-premarital-first-year',
    type: 'service',
    title: 'הכנה לנישואים וליווי בשנה הראשונה',
    body: 'פגישות הכנה לנישואים וליווי זוגי בשנה הראשונה. כסף, מגורים משותפים, חלוקת אחריות, משפחות, אינטימיות, ריבים ותיקון.',
    url: '/services/premarital-first-year',
    category: 'תחומי התמחות'
  },
  {
    id: 'service-couples-aliyah-relocation',
    type: 'service',
    title: 'ייעוץ זוגי לעולים ולזוגות ברילוקיישן',
    body: 'ייעוץ זוגי לפני עלייה או רילוקיישן, בזמן ההסתגלות ואחרי החזרה. שינוי תפקידים, קריירה, כסף, בדידות, שייכות ופערי הסתגלות.',
    url: '/services/couples-aliyah-relocation',
    category: 'תחומי התמחות'
  },
  {
    id: 'service-late-singleness',
    type: 'service',
    title: 'ייעוץ במצבי רווקות מאוחרת',
    body: 'ייעוץ אישי לרווקות ולרווקים סביב שחיקה, בדידות, לחץ מהסביבה, השוואה לאחרים, התמודדות עם דחייה ודפוסים חוזרים.',
    url: '/services/late-singleness',
    category: 'תחומי התמחות'
  },
  {
    id: 'service-finding-relationship',
    type: 'service',
    title: 'ליווי למציאת זוגיות',
    body: 'ליווי אישי סביב אפליקציות והיכרויות, דייטים, בחירת קשר, תקשורת בתחילת קשר, גבולות, הדדיות והמעבר מהיכרות לזוגיות.',
    url: '/services/finding-relationship',
    category: 'תחומי התמחות'
  },
  {
    id: 'service-gifted-parenting',
    type: 'service',
    title: 'הנחיית הורים לילדים מחוננים',
    body: 'ליווי הורים לילדים מחוננים סביב רגישות, פרפקציוניזם, שעמום, שייכות, מחוננות לצד ADHD והכנה רגשית וניהולית למסגרת מחוננים.',
    url: '/services/gifted-parenting',
    category: 'תחומי התמחות'
  },
  {
    id: 'service-aliyah-families',
    type: 'service',
    title: 'ייעוץ למשפחות עולים ותושבים חוזרים',
    body: 'ייעוץ זוגי והנחיית הורים למשפחות עולים לישראל ולתושבים חוזרים. הסתגלות, מסגרות חינוכיות, שינוי תפקידים, שגרה ושייכות.',
    url: '/services/aliyah-families',
    category: 'תחומי התמחות'
  }
];

const staticPages: SearchItem[] = [
  {
    id: 'page-about',
    type: 'page',
    title: 'אודות שירה סהרוני',
    body: 'שירה סהרוני, יועצת זוגית ומנחת הורים באשדוד ובאונליין. ליווי זוגות, הורים ומשפחות.',
    url: '/about',
    category: 'דפים'
  },
  {
    id: 'page-contact',
    type: 'page',
    title: 'צור קשר',
    body: 'יצירת קשר עם שירה בטלפון, WhatsApp או אימייל. השאירו הודעה ואחזור אליכם בהקדם.',
    url: '/contact',
    category: 'דפים'
  },
  {
    id: 'page-appointment',
    type: 'page',
    title: 'קביעת פגישת ייעוץ עם שירה',
    body: 'בחירת מועד לפגישת ייעוץ בת 50 דקות עם שירה סהרוני. ייעוץ זוגי או הנחיית הורים, באשדוד או אונליין.',
    url: '/appointment',
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
