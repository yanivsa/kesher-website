import { SITE_CONFIG } from './siteConfig';

const services = [
  {
    name: 'ייעוץ זוגי',
    path: '/services/couples',
    description: 'ייעוץ זוגי לשיפור התקשורת, התמודדות עם משברים וחיזוק הקשר.',
  },
  {
    name: 'הדרכת הורים',
    path: '/services/parenting',
    description: 'הדרכה להורים, לרבות הורות לילדים מחוננים ולילדים עם ADHD.',
  },
  {
    name: 'גישור',
    path: '/services/mediation',
    description: 'גישור לבני זוג ולמשפחות לצורך בניית הסכמות מעשיות.',
  },
  {
    name: 'הנחיית הורים לילדים מחוננים',
    path: '/services/gifted-parenting',
    description: 'הנחיית הורים סביב מחוננות, רגישות, שייכות ותפקודים ניהוליים.',
  },
  {
    name: 'ליווי משפחות עולים ותושבים חוזרים',
    path: '/services/aliyah-families',
    description: 'ייעוץ זוגי והנחיית הורים למשפחות בתקופת עלייה או חזרה לישראל.',
  },
  {
    name: 'ייעוץ זוגי לעולים ולזוגות ברילוקיישן',
    path: '/services/couples-aliyah-relocation',
    description: 'ייעוץ זוגי לפני מעבר מדינה, בתקופת ההסתגלות ולאחר החזרה.',
  },
  {
    name: 'הכנה לנישואים וליווי בשנה הראשונה',
    path: '/services/premarital-first-year',
    description: 'פגישות הכנה זוגיות סביב תקשורת, משפחה, בית וחלוקת אחריות.',
  },
  {
    name: 'ייעוץ במצבי רווקות מאוחרת',
    path: '/services/late-singleness',
    description: 'ייעוץ אישי סביב שחיקה, לחץ מהסביבה ודפוסים חוזרים.',
  },
  {
    name: 'ליווי למציאת זוגיות',
    path: '/services/finding-relationship',
    description: 'ליווי אישי סביב היכרויות, בחירת קשר, תקשורת וגבולות.',
  },
];

export const homeSchema = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'LocalBusiness',
      '@id': `${SITE_CONFIG.url}/#business`,
      name: SITE_CONFIG.author,
      alternateName: 'Shira Saharoni',
      url: `${SITE_CONFIG.url}/`,
      telephone: SITE_CONFIG.contact.phone,
      description: SITE_CONFIG.description,
      image: `${SITE_CONFIG.url}/images/shira-saharoni.webp`,
      priceRange: '$$',
      areaServed: [
        { '@type': 'City', name: 'אשדוד' },
        { '@type': 'Country', name: 'ישראל' },
      ],
      availableLanguage: 'he',
      address: {
        '@type': 'PostalAddress',
        addressLocality: 'אשדוד',
        addressCountry: 'IL',
      },
      knowsAbout: [
        'ייעוץ זוגי',
        'הנחיית הורים',
        'גישור',
        'ילדים מחוננים',
        'ADHD',
        'הכנה לנישואים',
        'משפחות עולים',
        'זוגיות ברילוקיישן',
        'רווקות מאוחרת',
      ],
      makesOffer: services.map((service) => ({
        '@type': 'Offer',
        itemOffered: {
          '@type': 'Service',
          name: service.name,
          url: `${SITE_CONFIG.url}${service.path}`,
          description: service.description,
        },
      })),
      potentialAction: {
        '@type': 'ReserveAction',
        target: {
          '@type': 'EntryPoint',
          urlTemplate: `${SITE_CONFIG.url}/appointment`,
          inLanguage: 'he',
        },
      },
    },
    {
      '@type': 'WebSite',
      '@id': `${SITE_CONFIG.url}/#website`,
      url: `${SITE_CONFIG.url}/`,
      name: SITE_CONFIG.title,
      description: SITE_CONFIG.description,
      publisher: { '@id': `${SITE_CONFIG.url}/#business` },
      inLanguage: 'he',
    },
    {
      '@type': 'Person',
      '@id': `${SITE_CONFIG.url}/#shira`,
      name: SITE_CONFIG.author,
      alternateName: 'Shira Saharoni',
      url: `${SITE_CONFIG.url}/about`,
      image: `${SITE_CONFIG.url}/images/shira-saharoni.webp`,
      jobTitle: ['יועצת זוגית', 'מנחת הורים', ],
      worksFor: { '@id': `${SITE_CONFIG.url}/#business` },
      knowsAbout: [
        'ייעוץ זוגי ומשפחתי',
        'הנחיית הורים קבוצתית ופרטנית',
        'הנחיית הורים עם התמחות ב־ADHD',
        'גישור',
      ],
    },
  ],
};
