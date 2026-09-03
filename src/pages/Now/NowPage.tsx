import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { FiClock, FiMapPin, FiHeart, FiBookOpen, FiUsers, FiCompass, FiCalendar } from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './NowPage.module.css';

const LAST_UPDATED = 'ספטמבר 2026';
const LAST_UPDATED_EN = 'September 2026';
const LAST_UPDATED_ISO = '2026-09-01';

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "ProfilePage",
      "@id": `${SITE_CONFIG.url}/now`,
      "url": `${SITE_CONFIG.url}/now`,
      "name": `עכשיו (Now Page) | שירה סהרוני`,
      "description": "מה שירה סהרוני עושה בימים אלה — קבלת זוגות לייעוץ וגישור, הנחיית הורים, פיתוח סדנאות וכתיבה מקצועית.",
      "dateCreated": "2026-09-01",
      "dateModified": LAST_UPDATED_ISO,
      "inLanguage": ["he-IL", "en-US"],
      "mainEntity": {
        "@type": "Person",
        "name": SITE_CONFIG.author,
        "alternateName": "Shira Saharoni",
        "jobTitle": ["יועצת זוגית", "מנחת הורים", "מגשרת מוסמכת"],
        "url": `${SITE_CONFIG.url}/about`,
        "sameAs": [
          SITE_CONFIG.links.facebook,
          SITE_CONFIG.links.instagram
        ]
      }
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
          "name": "עכשיו (Now)",
          "item": `${SITE_CONFIG.url}/now`
        }
      ]
    }
  ]
};

const NowPage: React.FC = () => {
  const [lang, setLang] = useState<'he' | 'en'>('he');

  return (
    <div className={styles.page}>
      <MetaTags
        title="מה אני עושה עכשיו (Now Page)"
        description="עמוד ה-Now של שירה סהרוני. הצצה לפעילויות, הפרויקטים והמיקוד המקצועי שלי בימים אלה: ייעוץ זוגי, גישור, הנחיית הורים והרצאות."
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.header}>
        <div className="container">
          <span className={styles.badge}>
            <FiClock aria-hidden="true" />
            {lang === 'he' ? 'תנועת NowNowNow' : 'Now Page Movement'}
          </span>
          <h1 className={styles.title}>
            {lang === 'he' ? 'מה אני עושה עכשיו' : "What I'm Doing Now"}
          </h1>
          <p className={styles.subtitle}>
            {lang === 'he'
              ? 'דף ציבורי ואישי המציג את המיקוד, הפרויקטים והעשייה שלי בימים אלו.'
              : 'A public snapshot of my current priorities, projects, and focus areas.'}
          </p>

          <div className={styles.langToggleContainer} role="group" aria-label="בחירת שפת תוכן">
            <button
              type="button"
              className={`${styles.langBtn} ${lang === 'he' ? styles.langBtnActive : ''}`}
              onClick={() => setLang('he')}
              aria-pressed={lang === 'he'}
            >
              עברית
            </button>
            <button
              type="button"
              className={`${styles.langBtn} ${lang === 'en' ? styles.langBtnActive : ''}`}
              onClick={() => setLang('en')}
              aria-pressed={lang === 'en'}
            >
              English
            </button>
          </div>
        </div>
      </header>

      <main className="container">
        <div className={styles.contentWrapper}>
          <article className={styles.card}>
            <div className={styles.metaHeader}>
              <div className={styles.metaItem}>
                <FiMapPin aria-hidden="true" />
                <span>{lang === 'he' ? 'אשדוד, ישראל (ומפגשי זום אונליין)' : 'Ashdod, Israel (and Zoom Online)'}</span>
              </div>
              <div className={styles.metaItem}>
                <FiClock aria-hidden="true" />
                <span>{lang === 'he' ? `עודכן לאחרונה: ${LAST_UPDATED}` : `Last updated: ${LAST_UPDATED_EN}`}</span>
              </div>
            </div>

            {lang === 'he' ? (
              <>
                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiHeart aria-hidden="true" />
                    קבלת זוגות לייעוץ וגישור
                  </h2>
                  <p>
                    בימים אלה אני מקבלת זוגות ויחידים בקליניקה באשדוד ובמפגשי זום אונליין ברחבי הארץ והעולם. המוקד המרכזי בעבודה הוא בניית תקשורת מקרבת, חידוש האינטימיות, ניהול קונפליקטים מורכבים והתמודדות עם משברי אמון ומעברי חיים.
                  </p>
                  <ul className={styles.list}>
                    <li><strong>ייעוץ זוגי:</strong> ליווי זוגות בשיפור התקשורת, פתרון קונפליקטים חוזרים וחיזוק הקשר.</li>
                    <li><strong>גישור משפחתי:</strong> עריכת הסכמי שלום בית ולחילופין פרידה בהסכמה בכבוד הדדי ובמינימום פגיעה בילדים.</li>
                    <li><strong>הכנה לנישואין והשנה הראשונה:</strong> הנחת יסודות יציבים לזוגות בתחילת הדרך המשותפת.</li>
                  </ul>
                </section>

                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiUsers aria-hidden="true" />
                    הנחיית הורים ומשפחות
                  </h2>
                  <p>
                    אני ממשיכה ללוות הורים במגוון אתגרים התפתחותיים ומשפחתיים:
                  </p>
                  <ul className={styles.list}>
                    <li>הדרכת הורים לילדים מחוננים ומצטיינים והתמודדות עם רגישות-יתר ופערים אסינכרוניים.</li>
                    <li>התמודדות משפחתית עם הפרעות קשב וריכוז (ADHD).</li>
                    <li>ליווי משפחות עולים ותושבים חוזרים בהתאקלמות רגשית, זוגית וחינוכית בישראל.</li>
                  </ul>
                </section>

                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiCompass aria-hidden="true" />
                    סדנאות, הרצאות ופעילות קהילתית
                  </h2>
                  <p>
                    מעבירה הרצאות וסדנאות לארגונים, קהילות ומרכזי הורות (כולל שיתוף פעולה מתמשך עם מרכז מהות אשדוד), בנושאי הורות מעצימה, תקשורת בינאישית, שחיקה הורית והתמודדות עם ADHD במשפחה.
                  </p>
                </section>

                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiBookOpen aria-hidden="true" />
                    כתיבה מקצועית ופיתוח כלים
                  </h2>
                  <p>
                    כותבת ומפרסמת באופן קבוע מאמרים ומדריכים מעשיים בבלוג האתר בנושאי זוגיות, הורות וגישור, ומשלבת כלים טכנולוגיים מתקדמים וסוכני מענה חכמים להנגשת ידע מקצועי מבוסס מחקר לקהל הרחב.
                  </p>
                </section>

                <div className={styles.callout}>
                  <p>מהו עמוד Now?</p>
                  <small>
                    עמוד זה נוצר בהשראת רעיון ה-Now Page של דרק סיברס (Derek Sivers). אם יש לכם אתר משלכם, מומלץ ליצור עמוד כזה גם אצלכם! פרטים נוספים באתר <a href="https://nownownow.com/about" target="_blank" rel="noopener noreferrer">nownownow.com</a>.
                  </small>
                </div>

                <div className={styles.ctaBox}>
                  <Link to="/appointment" className={styles.ctaBtn}>
                    <FiCalendar aria-hidden="true" />
                    <span>תיאום שיחת היכרות או פגישה</span>
                  </Link>
                </div>
              </>
            ) : (
              <div dir="ltr">
                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiHeart aria-hidden="true" />
                    Couples Counseling & Family Mediation
                  </h2>
                  <p>
                    I am currently seeing couples and individuals at my clinic in Ashdod, Israel, and online via Zoom worldwide. My core focus is helping partners build empathetic communication, rebuild emotional intimacy, navigate complex crises, and overcome repetitive conflicts.
                  </p>
                  <ul className={`${styles.list} ${styles.listEn}`}>
                    <li><strong>Couples Counseling:</strong> Guiding partners toward deeper connection, emotional security, and effective conflict resolution.</li>
                    <li><strong>Family Mediation:</strong> Facilitating amicable separation agreements or marital reconciliation (Shalom Bayit) with dignity and protection for children.</li>
                    <li><strong>Premarital & First-Year Counseling:</strong> Laying solid relational foundations for engaged and newlywed couples.</li>
                  </ul>
                </section>

                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiUsers aria-hidden="true" />
                    Parenting Guidance & Family Dynamics
                  </h2>
                  <p>
                    I provide active guidance to parents facing developmental, behavioral, and educational challenges:
                  </p>
                  <ul className={`${styles.list} ${styles.listEn}`}>
                    <li>Parenting gifted and twice-exceptional children, addressing asynchronous development and emotional intensity.</li>
                    <li>Managing ADHD within the family dynamic with practical coping strategies.</li>
                    <li>Supporting Olim (immigrant) and relocating families through educational and cultural transitions in Israel.</li>
                  </ul>
                </section>

                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiCompass aria-hidden="true" />
                    Lectures, Workshops & Community Work
                  </h2>
                  <p>
                    Conducting interactive workshops and lectures for community centers, organizations, and parenting hubs (including Mahut Ashdod Center) on positive parenting, emotional resilience, parental burnout, and ADHD.
                  </p>
                </section>

                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiBookOpen aria-hidden="true" />
                    Professional Writing & Digital Tools
                  </h2>
                  <p>
                    Authoring comprehensive guides and research-backed articles on my website blog, and implementing accessible digital tools to share actionable relationship and parenting insights.
                  </p>
                </section>

                <div className={`${styles.callout} ${styles.calloutEn}`}>
                  <p>What is a Now Page?</p>
                  <small>
                    This page was inspired by Derek Sivers&apos; public Now Page movement. If you have your own website, consider making one! Learn more at <a href="https://nownownow.com/about" target="_blank" rel="noopener noreferrer">nownownow.com</a>.
                  </small>
                </div>

                <div className={styles.ctaBox}>
                  <Link to="/appointment" className={styles.ctaBtn}>
                    <FiCalendar aria-hidden="true" />
                    <span>Book an Initial Consultation</span>
                  </Link>
                </div>
              </div>
            )}
          </article>
        </div>
      </main>
    </div>
  );
};

export default NowPage;
