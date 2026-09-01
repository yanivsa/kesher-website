import React from 'react';
import { Link } from 'react-router-dom';
import { FiUsers, FiExternalLink, FiAward, FiHeart, FiBook, FiGlobe, FiMail } from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './FriendsPage.module.css';

interface FriendResource {
  name: string;
  category: string;
  description: string;
  url: string;
  badge?: string;
}

const resources: Array<{
  categoryTitle: string;
  icon: React.ReactNode;
  items: FriendResource[];
}> = [
  {
    categoryTitle: 'איגודים וארגונים מקצועיים בישראל',
    icon: <FiAward className={styles.categoryIcon} aria-hidden="true" />,
    items: [
      {
        name: 'לשכת המגשרים בישראל',
        category: 'גישור ויישוב סכסוכים',
        description: 'הארגון היציג של קהילת המגשרים בישראל, הפועל להטמעת תרבות הגישור ויישוב סכסוכים בהסכמה במשפחה ובקהילה.',
        url: 'https://sulha.co.il'
      },
      {
        name: 'האגודה הישראלית לטיפול זוגי ומשפחתי',
        category: 'טיפול וייעוץ משפחתי',
        description: 'עמותה מקצועית המאגדת מטפלים ויועצים זוגיים ומשפחתיים מוסמכים בישראל ושומרת על סטנדרטים אתיים ומקצועיים.',
        url: 'https://www.mishpacha.org.il'
      }
    ]
  },
  {
    categoryTitle: 'גופי קהילה, רווחה ועיריות',
    icon: <FiHeart className={styles.categoryIcon} aria-hidden="true" />,
    items: [
      {
        name: 'מרכז מהות אשדוד',
        category: 'חוסן קהילתי והורות באשדוד',
        description: 'הרשות העירונית לחוסן קהילתי, מניעת התמכרויות והדרכת הורים באשדוד – שותפה בפעילויות והרצאות לתושבי העיר.',
        url: 'https://www.ashdod.muni.il'
      },
      {
        name: 'כל זכות - זכויות משפחה, הורות ורווחה',
        category: 'מידע ציבורי מונגש',
        description: 'מאגר המידע המקיף בישראל למיצוי זכויות בנושאי משפחה, גירושין, מזונות, ילדים עם צרכים מיוחדים ועולים חדשים.',
        url: 'https://www.kolzchut.org.il'
      },
      {
        name: 'עיריית אשדוד - אגף שירותים חברתיים',
        category: 'שירותי רווחה וקהילה',
        description: 'השירותים הקהילתיים והחברתיים הניתנים למשפחות, זוגות וילדים בעיר אשדוד ובמרחב הדרום.',
        url: 'https://www.ashdod.muni.il'
      }
    ]
  },
  {
    categoryTitle: 'הורות, חינוך מיוחד ומחוננים',
    icon: <FiBook className={styles.categoryIcon} aria-hidden="true" />,
    items: [
      {
        name: 'מכון אדלר בישראל',
        category: 'הנחיית הורים ויחסי משפחה',
        description: 'המוסד המוביל בישראל ללימודי הנחיית קבוצות הורים והטמעת הגישה האדלריאנית ליחסים משפחתיים מקרבים.',
        url: 'https://www.adler.org.il'
      },
      {
        name: 'עמותת קווים ומחשבות',
        category: 'קשב וריכוז (ADHD)',
        description: 'העמותה הישראלית להפרעת קשב (ADHD), המרכזת ידע מבוסס מחקר, סדנאות וכלים למשפחות, מורים ואנשי מקצוע.',
        url: 'https://www.keshev.org'
      },
      {
        name: 'האגף למחוננים ומצטיינים - משרד החינוך',
        category: 'ילדים מחוננים',
        description: 'פורטל ההורים והמידע הרשמי של משרד החינוך לאיתור, טיפוח ותמיכה רגשית ולימודית בתלמידים מחוננים ומצטיינים.',
        url: 'https://parents.education.gov.il'
      }
    ]
  },
  {
    categoryTitle: 'קהילות רשת ואינדקסים עצמאיים',
    icon: <FiGlobe className={styles.categoryIcon} aria-hidden="true" />,
    items: [
      {
        name: 'Slash Friends',
        category: 'רשת דפי חברים בינלאומית',
        description: 'אינדקס ופרויקט קהילתי המקדם את תרבות האינטרנט הפתוח ודפי שותפים וחברים באתרי אינטרנט עצמאיים.',
        url: 'https://slashfriends.org'
      },
      {
        name: 'NowNowNow (Derek Sivers)',
        category: 'תנועת עמודי ה-Now',
        description: 'התנועה הבינלאומית שהקים דרק סיברס לעידוד שקיפות ועדכון ציבורי על תחומי העיסוק הנוכחיים של אנשי מקצוע ויוצרים.',
        url: 'https://nownownow.com'
      }
    ]
  }
];

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "CollectionPage",
      "@id": `${SITE_CONFIG.url}/friends`,
      "url": `${SITE_CONFIG.url}/friends`,
      "name": `חברים, שותפים ומשאבים מומלצים | שירה סהרוני`,
      "description": "רשימת קישורים, ארגונים מקצועיים, קולגות ומקורות ידע מומלצים בתחומי הטיפול, הגישור וההורות בישראל.",
      "inLanguage": "he-IL"
    },
    {
      "@type": "BreadcrumbList",
      "itemListElement": [
        {
          "@type": "ListItem",
          "position": 1,
          "name": "עמוד הבית",
          "item": SITE_CONFIG.url
        },
        {
          "@type": "ListItem",
          "position": 2,
          "name": "חברים ומשאבים (Friends)",
          "item": `${SITE_CONFIG.url}/friends`
        }
      ]
    }
  ]
};

const FriendsPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags
        title="חברים, שותפים ומשאבים מומלצים (/friends)"
        description="רשימת קישורים מומלצים של שירה סהרוני: ארגונים מקצועיים, שירותי ייעוץ וגישור, מרכזים קהילתיים ומקורות מידע אמינים בישראל."
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.header}>
        <div className="container">
          <span className={styles.badge}>
            <FiUsers aria-hidden="true" />
            רשת שותפים ומקורות השראה
          </span>
          <h1 className={styles.title}>חברים, שותפים ומשאבים מומלצים</h1>
          <p className={styles.subtitle}>
            מאגר קישורים איכותי ומפרגן לארגונים מקצועיים, גופי קהילה, עמותות וקולגות בתחומי הייעוץ הזוגי, הגישור, בריאות הנפש וההורות בישראל.
          </p>
        </div>
      </header>

      <main className={styles.container}>
        {resources.map((sec, idx) => (
          <section key={idx} className={styles.categorySection}>
            <div className={styles.categoryHeader}>
              {sec.icon}
              <h2 className={styles.categoryTitle}>{sec.categoryTitle}</h2>
            </div>
            <div className={styles.grid}>
              {sec.items.map((item, itemIdx) => (
                <article key={itemIdx} className={styles.card}>
                  <div>
                    <h3 className={styles.cardTitle}>{item.name}</h3>
                    <p className={styles.cardDesc}>{item.description}</p>
                  </div>
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.cardLink}
                    aria-label={`ביקור באתר ${item.name} (נפתח בחלון חדש)`}
                  >
                    <span>ביקור באתר</span>
                    <FiExternalLink aria-hidden="true" />
                  </a>
                </article>
              ))}
            </div>
          </section>
        ))}

        <div className={styles.reciprocalNote}>
          <h3>קולגות ושותפים למקצוע?</h3>
          <p>
            אני מאמינה בשיתופי פעולה פוריים, הפניות הדדיות וחיזוק קהילת המטפלים והמגשרים בארץ. אם אתם מנהלים אתר מקצועי בתחום ומעוניינים להחליף המלצות או לשתף פעולה – אשמח לשמוע מכם.
          </p>
          <Link to="/contact" className={styles.contactLink}>
            <FiMail aria-hidden="true" />
            <span>צרו קשר לשיתוף פעולה</span>
          </Link>
        </div>
      </main>
    </div>
  );
};

export default FriendsPage;
