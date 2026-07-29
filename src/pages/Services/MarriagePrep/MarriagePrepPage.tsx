import React from 'react';
import { Link } from 'react-router-dom';
import { FiCheckCircle, FiHeart, FiShield, FiTrendingUp, FiMessageCircle, FiHome } from 'react-icons/fi';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from '../shared/SpecialtyServicePage.module.css';

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Service',
      name: 'הכנה לנישואים וליווי זוגי בשנה הראשונה',
      serviceType: 'ייעוץ זוגי והכנה לקראת חתונה',
      url: `${SITE_CONFIG.url}/services/marriage-preparation`,
      provider: {
        '@type': 'LocalBusiness',
        '@id': `${SITE_CONFIG.url}/#business`,
      },
      description: 'פגישות הכנה לנישואים וליווי מקצועי לשנה הראשונה. תיאום ציפיות, בניית תקשורת בריאה ומניעת משברים בחיים המשותפים.',
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
          name: 'הכנה לנישואים',
          item: `${SITE_CONFIG.url}/services/marriage-preparation`,
        },
      ],
    },
  ],
};

const MarriagePrepPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags
        title="הכנה לנישואים וליווי בשנה הראשונה"
        description="תכנון נכון של הזוגיות לפני החתונה: פגישות הכנה לנישואים וליווי לשנה הראשונה, למניעת משברים וביסוס תקשורת זוגית בריאה."
        image="/images/generated/site/marriage-prep-hero.jpg"
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.hero}>
        <div className={`container ${styles.heroGrid}`}>
          <div>
            <span className={styles.eyebrow}><FiHeart aria-hidden="true" /> בונים תשתית איתנה</span>
            <h1>הכנה לנישואים וליווי בשנה הראשונה</h1>
            <p className={styles.lead}>
              ההחלטה להתחתן היא מרגשת, אך מלווה באתגרים רבים. פגישות ההכנה והליווי לשנה הראשונה נועדו לתאם ציפיות, לבסס תקשורת מקרבת ולמנוע מראש את המוקשים המוכרים של תחילת החיים המשותפים.
            </p>
            <div className={styles.heroActions}>
              <Link to={SITE_CONFIG.links.appointment} className={styles.primaryButton}>קביעת פגישת הכנה</Link>
              <Link to="/contact" className={styles.secondaryButton}>יצירת קשר</Link>
            </div>
            <div style={{ marginTop: '1.5rem' }}>
              <Link to="/blog/premarital-questions-before-wedding" className={styles.textLink}>
                קראו עוד: 12 שאלות שחייבים לשאול לפני החתונה &larr;
              </Link>
            </div>
          </div>
          <aside className={styles.heroPanel} aria-label="מוקדי הליווי בהכנה לנישואים">
            <h2>למה צריך הכנה לנישואים?</h2>
            <ul className={styles.checkList}>
              <li>תיאום ציפיות פיננסי וכלכלי</li>
              <li>בניית כלים לפתרון קונפליקטים מראש</li>
              <li>גישור על פערים בין משפחות המוצא</li>
              <li>מניעת משברי השנה הראשונה לנישואים</li>
            </ul>
          </aside>
        </div>
      </header>

      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>שני שלבים של ביטחון זוגי</h2>
            <p>
              המסע שלכם מתחיל עוד לפני תכנון החתונה וממשיך עמוק אל תוך השנה הראשונה המשותפת. הליווי בנוי משני שלבים קריטיים שמשלימים זה את זה.
            </p>
          </div>
          <div className={styles.twoColumns}>
            <article className={styles.column}>
              <span className={styles.cardIcon}><FiShield aria-hidden="true" /></span>
              <h3>לפני החתונה: בניית תשתית</h3>
              <p>המרחב הבטוח לפתוח את כל הנושאים שמפחיד לדבר עליהם:</p>
              <ul className={styles.plainList}>
                <li>ניהול משק בית כלכלי משותף (חשבון משותף, חסכונות, רכישת בית)</li>
                <li>קריירה לעומת זמן משפחה – חלוקת תפקידים וזמנים</li>
                <li>משפחות המוצא: הצבת גבולות מול ההורים</li>
                <li>אינטימיות, מיניות ושמירה על הרומנטיקה בתוך השגרה</li>
                <li>תכנון משפחה וגידול ילדים</li>
              </ul>
            </article>
            <article className={styles.column}>
              <span className={styles.cardIcon}><FiTrendingUp aria-hidden="true" /></span>
              <h3>ליווי השנה הראשונה: צליחת המשבר</h3>
              <p>השנה הראשונה (שנת ההסתגלות) נחשבת למאתגרת ביותר סטטיסטית. נלמד איך:</p>
              <ul className={styles.plainList}>
                <li>להתמודד עם ההבדל בין "פנטזיית הנישואים" למציאות ביומיום</li>
                <li>לבסס שגרה זוגית שמכבדת גם את הלבד של כל אחד</li>
                <li>לזהות ולעצור "ריבים מתגלגלים" לפני שהם מחריפים</li>
                <li>לשמר שותפות חברית עמוקה מעבר למטלות הבית</li>
              </ul>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.softSection}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>נושאי הליבה: על מה באמת מדברים?</h2>
            <p>פגישות ההכנה הן פרקטיות וממוקדות מטרה, מתוך הבנה שכלים שנרכוש כעת יחסכו משברים עמוקים בעתיד.</p>
          </div>
          <div className={styles.cardGrid}>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiMessageCircle aria-hidden="true" /></span>
              <h3>תקשורת בזמן קונפליקט</h3>
              <p>איך לריב נכון? איך מפסיקים לנהל פנקסנות ומתחילים להקשיב לצרכים שמאחורי הכעס. כלים להורדת להבות ולמציאת פתרונות משותפים.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiHome aria-hidden="true" /></span>
              <h3>שותפות ועומס מנטלי</h3>
              <p>תכנון נכון של חלוקת התפקידים בבית, מעבר מעזרה הדדית ללקיחת אחריות משותפת, כדי שאף אחד לא ירגיש שהוא סוחב את העול לבד.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiCheckCircle aria-hidden="true" /></span>
              <h3>ערכים ומשמעות משותפת</h3>
              <p>בירור הערכים שמובילים אותנו: איך אנחנו רואים את השבת, את החגים, ואת החינוך שניתן לילדינו. יצירת זהות של ה\"אנחנו\" החדש.</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.softSection}>
        <div className="container">
          <div className={styles.highlight}>
            <h2>המתנה הכי טובה שתוכלו לתת לזוגיות שלכם</h2>
            <p>
              אנשים משקיעים חודשים וכספים רבים בתכנון ערב החתונה, אבל שוכחים להשקיע בחיים עצמם שמתחילים יום למחרת. ההכנה לנישואים מעניקה לכם רשת ביטחון וכלים מעשיים לשנים ארוכות ויפות יחד.
            </p>
          </div>
        </div>
      </section>

      <section className={styles.cta}>
        <div className="container">
          <h2>מתכננים חתונה? אל תחכו למשבר הראשון</h2>
          <p>פגישות ההכנה נערכות באשדוד או באונליין, ומותאמות אישית לצרכים ולסגנון שלכם.</p>
          <a href={SITE_CONFIG.links.whatsapp} className={styles.primaryButton}>שליחת הודעה לשירה להתייעצות</a>
        </div>
      </section>
    </div>
  );
};

export default MarriagePrepPage;
