import React from 'react';
import { Link } from 'react-router-dom';
import { FiUsers, FiExternalLink, FiHeart, FiBook, FiAward, FiMail, FiGlobe } from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './FriendsPage.module.css';

interface FriendEntry {
  name: string;
  role: string;
  url: string;
  description: string;
  displayUrl: string;
}

const personalFriends: FriendEntry[] = [
  {
    name: 'Derek Sivers',
    role: 'Author, Philosopher & Creator of NowNowNow',
    url: 'https://sivers.org',
    displayUrl: 'sivers.org',
    description: 'Creator of the /now page movement, CD Baby founder, and author of inspiring books on life, creativity, and business independence.'
  },
  {
    name: 'Nick Gray',
    role: 'Entrepreneur, Author & Creator of /friends',
    url: 'https://nickgray.net',
    displayUrl: 'nickgray.net',
    description: 'Author of The 2-Hour Cocktail Party, founder of Museum Hack, and champion of personal websites and the slashfriends directory.'
  },
  {
    name: 'Esther Perel',
    role: 'Psychotherapist & Relationship Author',
    url: 'https://estherperel.com',
    displayUrl: 'estherperel.com',
    description: 'World-renowned relationship therapist exploring modern intimacy, erotic intelligence, and emotional connection in couples.'
  },
  {
    name: 'The Gottman Institute (Drs. John & Julie Gottman)',
    role: 'Relationship & Marriage Research',
    url: 'https://www.gottman.com',
    displayUrl: 'gottman.com',
    description: 'Pioneering research-backed clinical methods for building lasting, healthy relationship communication and conflict resolution.'
  },
  {
    name: 'Austin Kleon',
    role: 'Writer & Visual Artist',
    url: 'https://austinkleon.com',
    displayUrl: 'austinkleon.com',
    description: 'Author of Steal Like an Artist and Show Your Work, writing weekly about art, creative habits, and maintaining a digital garden.'
  },
  {
    name: 'Seth Godin',
    role: 'Author & Daily Blogger',
    url: 'https://seths.blog',
    displayUrl: 'seths.blog',
    description: 'Daily insights on marketing, human connection, generosity, and authentic leadership since the early days of the web.'
  },
  {
    name: 'Yaniv Saharoni',
    role: 'Technologist, Cloud Architect & AI Strategist',
    url: 'https://yaniv.saharoni.com',
    displayUrl: 'yaniv.saharoni.com',
    description: 'My partner in life and technology, architecting innovative digital tools, AI automation, and cloud platforms.'
  }
];

const communityResources = [
  {
    title: 'איגודים מקצועיים וארגוני מומחים',
    icon: <FiAward className={styles.categoryIcon} aria-hidden="true" />,
    items: [
      {
        name: 'ארגון מגשרי ישראל',
        description: 'הבית המקצועי לקהילת המגשרים בישראל, פועל להטמעת תרבות הגישור ויישוב סכסוכים בהסכמה במשפחה ובקהילה.',
        url: 'https://www.israelmediators.org'
      },
      {
        name: 'האגודה הישראלית לטיפול זוגי ומשפחתי',
        description: 'עמותה מקצועית המאגדת מטפלים ויועצים זוגיים ומשפחתיים מוסמכים בישראל.',
        url: 'https://www.mishpacha.org.il'
      },
      {
        name: 'לשכת עורכי הדין בישראל',
        description: 'הגוף הסטטוטורי המאגד את עורכי הדין בישראל, כולל ועדות לענייני משפחה, גישור והסכמי ממון.',
        url: 'https://www.israelbar.org.il'
      }
    ]
  },
  {
    title: 'הורות, חוסן וחינוך מיוחד',
    icon: <FiBook className={styles.categoryIcon} aria-hidden="true" />,
    items: [
      {
        name: 'מרכז מהות אשדוד',
        description: 'הרשות העירונית לחוסן קהילתי, מניעת התמכרויות והדרכת הורים באשדוד – שותפה בפעילויות והרצאות לתושבי העיר.',
        url: 'https://www.ashdod.muni.il'
      },
      {
        name: 'עמותת קווים ומחשבות',
        description: 'העמותה הישראלית להפרעת קשב (ADHD), המרכזת ידע מבוסס מחקר וכלים מעשיים למשפחות ואנשי חינוך.',
        url: 'https://www.keshev.org'
      },
      {
        name: 'האגף למחוננים ומצטיינים - משרד החינוך',
        description: 'פורטל המידע הרשמי של משרד החינוך לאיתור, טיפוח ותמיכה רגשית ולימודית בתלמידים מחוננים ומצטיינים.',
        url: 'https://parents.education.gov.il'
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
      "name": "Friends & Sites I Like (/friends) | שירה סהרוני",
      "description": "A /friends page listing personal websites, creators, and colleagues I like, follow, and recommend.",
      "inLanguage": ["en-US", "he-IL"]
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
          "name": "Friends (/friends)",
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
        title="Friends & Sites I Like (/friends) | שירה סהרוני"
        description="My /friends page: personal websites, creators, authors, and inspiring people I follow and recommend. Part of the Slash Friends movement."
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.header}>
        <div className="container">
          <span className={styles.badge}>
            <FiUsers aria-hidden="true" />
            /friends page • Slash Friends Movement
          </span>
          <h1 className={styles.title}>Friends & Sites I Like (/friends)</h1>
          <p className={styles.subtitle}>
            This is my public <strong>/friends</strong> page — inspired by the indie web blogroll revival and the <a href="https://slashfriends.org" target="_blank" rel="noopener noreferrer" style={{color: 'inherit', textDecoration: 'underline'}}>/friends standard</a>. Here are personal websites, creators, and mentors whose work, writing, and philosophy inspire me.
          </p>
          <p style={{marginTop: '0.5rem', color: 'var(--color-text-muted)', fontSize: '0.95rem'}}>
            עמוד החברים וההמלצות האישי שלי: קישורים לאנשים, יוצרים, חוקרים ועמיתים שאת האתרים והרעיונות שלהם אני מעריכה ועוקבת אחריהם באהבה.
          </p>
        </div>
      </header>

      <main className={styles.container}>
        {/* Main Friends List */}
        <section className={styles.categorySection}>
          <div className={styles.categoryHeader}>
            <FiHeart className={styles.categoryIcon} aria-hidden="true" />
            <h2 className={styles.categoryTitle}>Friends, Creators & Sites I Follow</h2>
          </div>
          <div className={styles.grid}>
            {personalFriends.map((friend, idx) => (
              <article key={idx} className={styles.card}>
                <div>
                  <h3 className={styles.cardTitle}>{friend.name}</h3>
                  <div style={{fontSize: '0.85rem', color: 'var(--color-primary-dark)', fontWeight: 600, marginBottom: '0.5rem'}}>
                    {friend.role}
                  </div>
                  <p className={styles.cardDesc}>{friend.description}</p>
                </div>
                <a
                  href={friend.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.cardLink}
                  aria-label={`Visit ${friend.name}'s website (${friend.displayUrl})`}
                >
                  <span>{friend.displayUrl}</span>
                  <FiExternalLink aria-hidden="true" />
                </a>
              </article>
            ))}
          </div>
        </section>

        {/* Community & Professional Resources */}
        {communityResources.map((sec, idx) => (
          <section key={idx} className={styles.categorySection}>
            <div className={styles.categoryHeader}>
              {sec.icon}
              <h2 className={styles.categoryTitle}>{sec.title}</h2>
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
                    aria-label={`ביקור באתר ${item.name}`}
                  >
                    <span>ביקור באתר</span>
                    <FiExternalLink aria-hidden="true" />
                  </a>
                </article>
              ))}
            </div>
          </section>
        ))}

        {/* Reciprocal Section */}
        <div className={styles.reciprocalNote}>
          <FiGlobe style={{fontSize: '2rem', color: 'var(--color-primary)', marginBottom: '0.5rem'}} aria-hidden="true" />
          <h3>Got a personal website or /friends page? / מעוניינים להחליף המלצות?</h3>
          <p>
            Linking out makes the web better! If you are a therapist, educator, creator, or friend with your own personal site and would like to connect or exchange links, I would love to hear from you.
          </p>
          <Link to="/contact" className={styles.contactLink}>
            <FiMail aria-hidden="true" />
            <span>צרו קשר לשיתוף קישורים והמלצות</span>
          </Link>
        </div>
      </main>
    </div>
  );
};

export default FriendsPage;
