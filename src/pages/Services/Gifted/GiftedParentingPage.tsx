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
      image: `${SITE_CONFIG.url}/images/generated/services/parenting-room.jpg`,
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
    {
      '@type': 'FAQPage',
      mainEntity: [
        {
          '@type': 'Question',
          name: 'מהי הנחיית הורים לילדים מחוננים ומתי כדאי לפנות?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'הנחיית הורים לילדים מחוננים מספקת כלים מעשיים להתמודדות עם הפער בין היכולת הקוגניטיבית הגבוהה לבין הבשלות הרגשית, הפרפקציוניזם, קשיי הוויסות והאתגרים החברתיים. מומלץ לפנות כאשר מזהים תסכול סביב משימות יומיום, התפרצויות זעם, שעמום בבית הספר או לקראת כניסה למסגרת מחוננים.'
          }
        },
        {
          '@type': 'Question',
          name: 'איך מתמודדים עם שילוב של מחוננות והפרעת קשב וריכוז (ADHD)?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'במקרים של כפל ייחודיות (2e), היכולת הגבוהה עלולה להסוות את קשיי הקשב, או שקשיי ההתארגנות יוצרים תסכול עמוק. בהנחיית ההורים מפרידים בין מוטיבציה לתפקודים ניהוליים ובונים עוגנים פשוטים לניהול זמן, משימות ושגרה בלי מאבקי כוח.'
          }
        },
        {
          '@type': 'Question',
          name: 'מה ההבדל בין הנחיית הורים לטיפול רגשי בילד?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'הנחיית הורים מתמקדת בסביבה הטבעית של הילד — הבית והמשפחה. ההורים מקבלים כלים לשנות את הדינמיקה היומיומית, להציב גבולות מותאמים ולתמוך בוויסות, מה שמייצר השפעה ישירה ומהירה על איכות החיים בלי להעמיס על הילד מפגש טיפולי נוסף.'
          }
        }
      ]
    }
  ],
};

const GiftedParentingPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags
        title="הנחיית הורים לילדים מחוננים"
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
              <Link to={SITE_CONFIG.links.appointment} className={styles.primaryButton}>קביעת פגישת ייעוץ</Link>
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

      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>מאמרי עומק וכלים מעשיים להורים</h2>
            <p>קריאה מקצועית נוספת בנושאי מחוננות, תפקודים ניהוליים וקשב:</p>
          </div>
          <div className={styles.cardGrid}>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiBookOpen aria-hidden="true" /></span>
              <h3><Link to="/blog/gifted-adhd-executive-functions-struggle">מחוננות לצד הפרעת קשב וקשיי התארגנות</Link></h3>
              <p>הילד מחונן אבל שוכח את התיק? להבין מה קורה כשיכולת גבוהה פוגשת קושי בתפקודים ניהוליים.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiHeart aria-hidden="true" /></span>
              <h3><Link to="/blog/gifted-children-perfectionism-tears">התמודדות עם פרפקציוניזם ופחד מכישלון</Link></h3>
              <p>כשהעיפרון מחליק והדף נקרע: כלים לסיוע לילד שמתקשה לשאת טעויות או חוסר הצלחה מיידית.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiLayers aria-hidden="true" /></span>
              <h3><Link to="/blog/gifted-children-framework-preparation">הכנה רגשית לכניסה למסגרת מחוננים</Link></h3>
              <p>התקבלתם למסגרת מחוננים? איך להפחית חרדה, לבנות ציפיות מאוזנות וללוות את המעבר ברגישות.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiTarget aria-hidden="true" /></span>
              <h3><Link to="/blog/smart-youth-focus-tasks-organization">ילד נבון מאוד שמתקשה במשימות שגרתיות</Link></h3>
              <p>איך לגשר על הפער בין הבנה מהירה לבין קושי להתמיד במשימות יומיומיות שאינן מרתקות.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiUsers aria-hidden="true" /></span>
              <h3><Link to="/blog/gifted-children-social-difficulties">ילדים מחוננים וקשיים חברתיים</Link></h3>
              <p>הפער בין השכל לרגש: איך לסייע לילד לפתח קשרים חברתיים מספקים בלי לוותר על מי שהוא.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiCompass aria-hidden="true" /></span>
              <h3><Link to="/blog/adhd-first-grade-preparation">הכנה לכיתה א לילדים עם ADHD</Link></h3>
              <p>תוכנית ביתית מעשית לבניית שגרה, תפקודים ניהוליים ועצמאות לקראת המעבר לבית הספר.</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.softSection}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>שאלות נפוצות על הנחיית הורים למחוננים</h2>
            <p>תשובות לשאלות מרכזיות המעסיקות הורים בתהליך:</p>
          </div>
          <div className={styles.cardGrid}>
            <article className={styles.card}>
              <h3>מהי הנחיית הורים למחוננים ומתי כדאי לפנות?</h3>
              <p>הנחיית הורים לילדים מחוננים מספקת כלים מעשיים להתמודדות עם הפער בין היכולת הקוגניטיבית הגבוהה לבין הבשלות הרגשית, הפרפקציוניזם, קשיי הוויסות והאתגרים החברתיים. מומלץ לפנות כאשר מזהים תסכול סביב משימות יומיום, התפרצויות זעם או לקראת כניסה למסגרת מחוננים.</p>
            </article>
            <article className={styles.card}>
              <h3>איך מתמודדים עם שילוב של מחוננות ו-ADHD?</h3>
              <p>במקרים של כפל ייחודיות (2e), היכולת הגבוהה עלולה להסוות את קשיי הקשב, או שקשיי ההתארגנות יוצרים תסכול עמוק. בהנחיית ההורים מפרידים בין מוטיבציה לתפקודים ניהוליים ובונים עוגנים פשוטים לשגרה בלי מאבקי כוח.</p>
            </article>
            <article className={styles.card}>
              <h3>מה ההבדל בין הנחיית הורים לטיפול רגשי בילד?</h3>
              <p>הנחיית הורים מתמקדת בסביבה הטבעית של הילד — הבית והמשפחה. ההורים מקבלים כלים לשנות את הדינמיקה היומיומית, להציב גבולות מותאמים ולתמוך בוויסות, מה שמייצר השפעה ישירה ומהירה בלי להעמיס על הילד מפגש נוסף.</p>
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
