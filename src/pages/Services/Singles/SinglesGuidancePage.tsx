import React from 'react';
import { Link } from 'react-router-dom';
import {
  FiCheckCircle,
  FiCompass,
  FiHeart,
  FiMessageCircle,
  FiRefreshCw,
  FiSearch,
  FiUser,
} from 'react-icons/fi';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from '../shared/SpecialtyServicePage.module.css';

const blogHref = '/blog?category=זוגיות&subcategory=רווקות מאוחרת ומציאת זוגיות';

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Service',
      name: 'ייעוץ ברווקות מאוחרת וליווי למציאת זוגיות',
      serviceType: 'ייעוץ אישי וליווי בתהליך היכרות ובניית זוגיות',
      url: `${SITE_CONFIG.url}/services/singles-guidance`,
      provider: {
        '@type': 'LocalBusiness',
        '@id': `${SITE_CONFIG.url}/#business`,
      },
      description: 'ייעוץ אישי לרווקות ולרווקים סביב דייטים, בחירת קשר, תקשורת, גבולות ושחיקה בתהליך מציאת זוגיות, באשדוד ובאונליין.',
      areaServed: 'ישראל',
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: 'עמוד הבית',
          item: SITE_CONFIG.url,
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: 'רווקות מאוחרת ומציאת זוגיות',
          item: `${SITE_CONFIG.url}/services/singles-guidance`,
        },
      ],
    },
  ],
};

const SinglesGuidancePage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags
        title="ייעוץ ברווקות מאוחרת וליווי למציאת זוגיות | שירה סהרוני"
        description="ליווי אישי לרווקות ולרווקים סביב דייטים, בחירת קשר, תקשורת, גבולות ושחיקה בדרך לזוגיות — באשדוד ובאונליין."
        image="/images/generated/services/couples-room.jpg"
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.hero}>
        <div className={`container ${styles.heroGrid}`}>
          <div>
            <span className={styles.eyebrow}><FiHeart aria-hidden="true" /> ליווי אישי בדרך לזוגיות</span>
            <h1>ייעוץ ברווקות מאוחרת וליווי למציאת זוגיות</h1>
            <p className={styles.lead}>
              כשכבר היו לא מעט היכרויות, עצות מהסביבה ואכזבות, קל להגיע לדייט הבא עייפים או דרוכים. בליווי אפשר לעצור, להבין מה חוזר על עצמו ולבחור דרך שמתאימה לכם — בלי להפוך את החיפוש לעבודה במשרה נוספת.
            </p>
            <div className={styles.heroActions}>
              <Link to={SITE_CONFIG.links.appointment} className={styles.primaryButton}>קביעת פגישת ייעוץ</Link>
              <Link to={blogHref} className={styles.secondaryButton}>מאמרים בנושא</Link>
            </div>
          </div>
          <aside className={styles.heroPanel} aria-label="נושאים מרכזיים בליווי">
            <h2>אפשר להגיע עם מה שמעסיק אתכם עכשיו</h2>
            <ul className={styles.checkList}>
              <li>שחיקה, לחץ או הימנעות מדייטים</li>
              <li>קושי לבחור למי לתת הזדמנות</li>
              <li>קשרים שמתחילים ונעצרים באותה נקודה</li>
              <li>רצון להכיר בלי לאבד את עצמכם בדרך</li>
            </ul>
          </aside>
        </div>
      </header>

      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>לא כל קושי בחיפוש זוגיות הוא אותו קושי</h2>
            <p>
              לפעמים השאלה היא איפה ואיך להכיר. לפעמים האתגר מתחיל דווקא אחרי שיש חיבור. בפגישות נבדוק את המצב שלכם, בלי רשימת כללים אחידה ובלי להבטיח שתהליך אישי יכול לשלוט בתזמון של היכרות.
            </p>
          </div>
          <div className={styles.cardGrid}>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiSearch aria-hidden="true" /></span>
              <h3>עייפות מהחיפוש</h3>
              <p>כשהאפליקציות, ההודעות והדייטים מתחילים להרגיש כמו רצף מטלות, בודקים איך לצמצם עומס ולבחור קצב שאפשר להתמיד בו.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiCompass aria-hidden="true" /></span>
              <h3>בחירה והתאמה</h3>
              <p>מחדדים מה באמת חשוב לכם בקשר, על מה אפשר להתגמש ואילו סימנים דורשים עוד בירור לפני שממשיכים או נפרדים.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiMessageCircle aria-hidden="true" /></span>
              <h3>תקשורת בתחילת קשר</h3>
              <p>מתרגלים איך לשאול, לבטא עניין, להציב גבול ולדבר על ציפיות בלי להעמיד פנים שהכול קליל כשבפנים יש חוסר ודאות.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiRefreshCw aria-hidden="true" /></span>
              <h3>דפוס שחוזר</h3>
              <p>מסתכלים על נקודות שבהן קשרים נתקעים: למי אתם נמשכים, מתי אתם נסגרים ומה קורה כשמישהו אחר דווקא מתקרב.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiUser aria-hidden="true" /></span>
              <h3>לחץ מהסביבה</h3>
              <p>בונים תשובות וגבולות לשאלות מהמשפחה ומהחברים, כדי שהדאגה שלהם לא תנהל את הקצב ואת הבחירות שלכם.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiCheckCircle aria-hidden="true" /></span>
              <h3>מעבר מהיכרות לקשר</h3>
              <p>בודקים איך לתת לקשר זמן להתפתח ובמקביל לשים לב להדדיות, לזמינות וליכולת לדבר על דברים שאינם מושלמים.</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.softSection}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>איך נראה הליווי?</h2>
            <p>זהו ייעוץ אישי וממוקד. לא שידוך ולא נוסחה למציאת בן או בת זוג, אלא עבודה משותפת על החלקים שנמצאים בידיים שלכם.</p>
          </div>
          <div className={styles.processGrid}>
            <article className={styles.processStep}>
              <h3>מבינים מה קורה היום</h3>
              <p>עוברים על דרך ההיכרות, החוויות האחרונות, מה עובד ומה כבר גובה מכם יותר מדי אנרגיה.</p>
            </article>
            <article className={styles.processStep}>
              <h3>בוחרים נושא אחד לעבודה</h3>
              <p>למשל סינון מוקדם, שיחה בדייט, הבעת עניין, התמודדות עם דחייה או החלטה אם להמשיך קשר.</p>
            </article>
            <article className={styles.processStep}>
              <h3>מנסים ובודקים</h3>
              <p>מגיעים עם מה שקרה בפועל, מדייקים את התגובה הבאה ולא הופכים כל דייט למבחן של הצלחה או כישלון.</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.softSection}>
        <div className="container">
          <div className={styles.highlight}>
            <h2>מאמרים על רווקות, דייטים ובניית קשר</h2>
            <p>
              בבלוג מתפרסמים מדריכים בעברית טבעית על שחיקה מהיכרויות, התלבטויות בתחילת קשר, תקשורת, גבולות והבחנה בין פשרה בריאה לוויתור על צורך חשוב.
            </p>
            <Link to={blogHref} className={styles.secondaryButton}>לכל המאמרים בתחום</Link>
          </div>
        </div>
      </section>

      <section className={styles.cta}>
        <div className="container">
          <h2>אפשר לבדוק יחד מה נכון לכם עכשיו</h2>
          <p>הפגישות מתקיימות באשדוד או אונליין, בקצב שמתאים למטרה ולמצב שלכם.</p>
          <a href={SITE_CONFIG.links.whatsapp} className={styles.primaryButton}>שליחת הודעה לשירה</a>
        </div>
      </section>
    </div>
  );
};

export default SinglesGuidancePage;
