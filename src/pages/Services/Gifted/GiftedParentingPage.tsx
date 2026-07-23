import React from 'react';
import { Link } from 'react-router-dom';
import { FiBookOpen, FiCompass, FiHeart, FiLayers, FiTarget, FiUsers } from 'react-icons/fi';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from '../shared/SpecialtyServicePage.module.css';

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Service',
      name: 'הנחיית הורים לילדים מחוננים',
      serviceType: 'הנחיית הורים לילדים מחוננים והכנה למסגרת מחוננים',
      url: `${SITE_CONFIG.url}/services/gifted-parenting`,
      provider: {
        '@type': 'LocalBusiness',
        '@id': `${SITE_CONFIG.url}/#business`,
      },
      description: 'הנחיית הורים לילדים מחוננים באשדוד ובאונליין, כולל מחוננות לצד ADHD והכנה רגשית וניהולית למסגרת מחוננים.',
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
          name: 'הנחיית הורים לילדים מחוננים',
          item: `${SITE_CONFIG.url}/services/gifted-parenting`,
        },
      ],
    },
  ],
};

const GiftedParentingPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags
        title="הנחיית הורים לילדים מחוננים | שירה סהרוני"
        description="ליווי הורים לילדים מחוננים: רגישות, פרפקציוניזם, שייכות, מחוננות לצד ADHD והכנה רגשית וניהולית למסגרת מחוננים."
        image="/images/generated/services/parenting-room.jpg"
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.hero}>
        <div className={`container ${styles.heroGrid}`}>
          <div>
            <span className={styles.eyebrow}><FiBookOpen aria-hidden="true" /> תחום ליווי מרכזי</span>
            <h1>הנחיית הורים לילדים מחוננים</h1>
            <p className={styles.lead}>
              ילד מחונן אינו רק ילד שלומד מהר יותר. לעיתים היכולת הגבוהה מגיעה לצד רגישות, פרפקציוניזם, שעמום, קושי חברתי או פער בין מה שהילד מבין לבין מה שהוא עדיין מסוגל לנהל.
            </p>
            <div className={styles.heroActions}>
              <a href={SITE_CONFIG.links.whatsapp} className={styles.primaryButton}>לתיאום שיחת היכרות</a>
              <Link to="/services/parenting" className={styles.secondaryButton}>לכל תחומי הנחיית ההורים</Link>
            </div>
          </div>
          <aside className={styles.heroPanel} aria-label="נושאים מרכזיים בליווי">
            <h2>במה אפשר להתמקד?</h2>
            <ul className={styles.checkList}>
              <li>פער בין יכולת גבוהה לבשלות רגשית</li>
              <li>פרפקציוניזם, תסכול ורגישות גבוהה</li>
              <li>שייכות חברתית ותקשורת עם המסגרת</li>
              <li>מחוננות לצד ADHD ואתגרי קשב</li>
            </ul>
          </aside>
        </div>
      </header>

      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>כשהיכולת הגבוהה אינה מספרת את כל הסיפור</h2>
            <p>
              בהנחיית ההורים נבנה דרך שמתאימה לילד שלכם — בלי להקטין את היכולות שלו ובלי להעמיס עליו ציפיות שאינן מותאמות לגילו ולצרכיו.
            </p>
          </div>
          <div className={styles.cardGrid}>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiHeart aria-hidden="true" /></span>
              <h3>רגישות ופרפקציוניזם</h3>
              <p>עבודה הורית סביב פחד מטעויות, תגובות עוצמתיות, ביקורת עצמית והצורך להרגיש בטוח גם כשלא מצליחים מיד.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiTarget aria-hidden="true" /></span>
              <h3>מוטיבציה ושעמום</h3>
              <p>הבחנה בין חוסר עניין, עומס וקושי להתמיד, ובניית אתגר מתאים שאינו הופך כל משימה למאבק.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiUsers aria-hidden="true" /></span>
              <h3>שייכות חברתית</h3>
              <p>תיווך מצבים חברתיים, התמודדות עם תחושת שונות וחיזוק היכולת ליצור קשרים בלי לוותר על מי שהילד.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiLayers aria-hidden="true" /></span>
              <h3>גבולות ושגרה</h3>
              <p>בניית שגרה, עצמאות וכללים משפחתיים גם כשהילד שואל שאלות מורכבות, מתווכח היטב או מתקשה לקבל גבול.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiCompass aria-hidden="true" /></span>
              <h3>קשר עם הצוות החינוכי</h3>
              <p>דיוק הצרכים של הילד ויצירת תקשורת עניינית עם המסגרת, תוך שמירה על שותפות ועל ראייה רחבה.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiBookOpen aria-hidden="true" /></span>
              <h3>מחוננות לצד ADHD</h3>
              <p>בניית תמיכה שמתייחסת גם ליכולת הגבוהה וגם לקשיי התארגנות, ויסות, ניהול זמן והתמדה.</p>
            </article>
          </div>
        </div>
      </section>

      <section id="gifted-framework" className={styles.softSection}>
        <div className="container">
          <div className={styles.highlight}>
            <h2>הכנה לכניסה למסגרת מחוננים</h2>
            <p>
              המעבר למסגרת מחוננים יכול להיות מרגש וגם מערער. ההכנה משלבת את הצד הניהולי והרגשי: הבנת השינוי, ניהול עומס והתארגנות, התמודדות עם ציפיות והשוואה לאחרים, הכנה חברתית ושיח מותאם על מחוננות וזהות.
            </p>
          </div>
          <div className={styles.twoColumns}>
            <article className={styles.column}>
              <h3>הצד של הילד</h3>
              <ul className={styles.plainList}>
                <li>היכרות עם השינוי והפחתת אי־ודאות</li>
                <li>ניהול משימות, ציוד, זמן ועומס</li>
                <li>התמודדות עם טעויות ועם חשש מכישלון</li>
                <li>הכנה רגשית וחברתית למסגרת החדשה</li>
              </ul>
            </article>
            <article className={styles.column}>
              <h3>הצד של ההורים</h3>
              <ul className={styles.plainList}>
                <li>תמיכה בלי לחץ מיותר</li>
                <li>שיח משפחתי מאוזן על מחוננות</li>
                <li>בניית שגרה שמאפשרת גם מנוחה ופנאי</li>
                <li>תקשורת מתואמת עם הצוות החינוכי</li>
              </ul>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.softSection}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>איך נראה הליווי?</h2>
            <p>התהליך מתחיל בהבנת הילד והמשפחה, ומתקדם לצעדים קטנים שניתן לתרגל בבית ובקשר עם המסגרת.</p>
          </div>
          <div className={styles.processGrid}>
            <article className={styles.processStep}>
              <h3>ממפים את התמונה</h3>
              <p>מזהים את החוזקות, מוקדי הקושי, המצבים החוזרים והציפיות של הילד, ההורים והמסגרת.</p>
            </article>
            <article className={styles.processStep}>
              <h3>בוחרים מוקד מעשי</h3>
              <p>מגדירים מטרה ברורה ומפתחים כלים המתאימים לגיל הילד, לאופי שלו ולשגרת המשפחה.</p>
            </article>
            <article className={styles.processStep}>
              <h3>מתרגלים ומדייקים</h3>
              <p>בודקים מה עוזר בפועל, מתאימים את הדרך ומחזקים בהדרגה עצמאות, ביטחון ושיתוף פעולה.</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.cta}>
        <div className="container">
          <h2>לא צריך לבחור בין היכולת לרווחה של הילד</h2>
          <p>אפשר לבנות דרך שמכבדת את הכישרון, את הקצב ואת הצרכים של כל המשפחה.</p>
          <a href={SITE_CONFIG.links.whatsapp} className={styles.primaryButton}>שיחה עם שירה</a>
        </div>
      </section>
    </div>
  );
};

export default GiftedParentingPage;
