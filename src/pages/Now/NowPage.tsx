import React, { useState } from 'react';
import { FiClock, FiMapPin, FiHeart, FiBookOpen, FiUsers, FiCompass } from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './NowPage.module.css';

const LAST_UPDATED = 'ספטמבר 2026';
const LAST_UPDATED_EN = 'September 2026';
const LAST_UPDATED_ISO = '2026-09-02';

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "ProfilePage",
      "@id": `${SITE_CONFIG.url}/now`,
      "url": `${SITE_CONFIG.url}/now`,
      "name": `עכשיו (Now Page) | שירה סהרוני`,
      "description": "עדכון אישי של שירה סהרוני על הנושאים, השאלות והעשייה שמעסיקים אותה בתקופה הזו.",
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
        title="מה מעסיק אותי עכשיו (Now Page)"
        description="עמוד ה-Now האישי של שירה סהרוני: במה אני מתמקדת, אילו שאלות מלוות אותי ומה אני לומדת וכותבת בתקופה הזו."
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.header}>
        <div className="container">
          <span className={styles.badge}>
            <FiClock aria-hidden="true" />
            {lang === 'he' ? 'תנועת NowNowNow' : 'Now Page Movement'}
          </span>
          <h1 className={styles.title}>
            {lang === 'he' ? 'מה מעסיק אותי עכשיו' : "What's On My Mind Now"}
          </h1>
          <p className={styles.subtitle}>
            {lang === 'he'
              ? 'כמה מילים אישיות על העבודה, השאלות והרעיונות שנמצאים איתי בתקופה הזו.'
              : 'A personal note about the work, questions, and ideas that are with me these days.'}
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
                    הקשבה למה שקורה בין אנשים
                  </h2>
                  <p>
                    בתקופה הזו אני פוגשת בקליניקה באשדוד ובזום זוגות, יחידים ומשפחות שנמצאים בצמתים שונים. מה שמעסיק אותי במיוחד הוא הרגע שבו שיחה חוזרת שוב ושוב לאותו מקום — והאפשרות לעצור, להקשיב אחרת ולזהות צעד קטן שיכול לשנות את הכיוון.
                  </p>
                  <p>
                    אני חושבת הרבה על המתח שבין הרצון לפתור דברים מהר לבין הצורך לתת מקום למה שלא נאמר עדיין. בעיניי, זו אחת השאלות החשובות בעבודה זוגית, הורית ובגישור.
                  </p>
                </section>

                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiUsers aria-hidden="true" />
                    הורות בתוך החיים האמיתיים
                  </h2>
                  <p>
                    אני ממשיכה ללמוד מהורים שמתמודדים עם עומס, הפרעת קשב, רגישות גבוהה, מחוננות ומעברים משפחתיים. המיקוד שלי עכשיו הוא בתרגום של רעיונות גדולים לצעדים שאפשר באמת לנסות בבית — גם כשהיום עמוס, כשאין תשובה מושלמת וכשכל ילד זקוק למשהו מעט אחר.
                  </p>
                </section>

                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiCompass aria-hidden="true" />
                    מפגש עם קהילה
                  </h2>
                  <p>
                    במפגשים, בהרצאות ובסדנאות באשדוד ומחוצה לה אני חוזרת שוב ושוב לשאלה איך יוצרים שיחה שמאפשרת לאנשים לא רק לקבל ידע, אלא גם לזהות את עצמם בתוכו. המפגש הקבוצתי מזכיר לי כמה הקלה יש בגילוי שאנחנו לא היחידים שמתמודדים עם קושי מסוים.
                  </p>
                </section>

                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiBookOpen aria-hidden="true" />
                    כתיבה, למידה ופיתוח כלים
                  </h2>
                  <p>
                    אני אוספת שאלות שחוזרות בחדר ובקהילה והופכת אותן בהדרגה למאמרים ולמדריכים מעשיים. לצד הכתיבה אני בוחנת כיצד מחקר וכלים דיגיטליים יכולים להנגיש ידע בלי לאבד את המורכבות האנושית שלו. כרגע מעניינת אותי במיוחד כתיבה שמצליחה להיות גם מדויקת וגם שימושית ביום־יום.
                  </p>
                </section>

                <div className={styles.callout}>
                  <p>מהו עמוד Now?</p>
                  <small>
                    זהו צילום מצב, לא רשימת שירותים. עמוד זה נוצר בהשראת רעיון ה-Now Page של דרק סיברס (Derek Sivers): מה הייתי מספרת לחברה שלא פגשתי כבר שנה. פרטים נוספים באתר <a href="https://nownownow.com/about" target="_blank" rel="noopener noreferrer">nownownow.com</a>.
                  </small>
                </div>
              </>
            ) : (
              <div dir="ltr">
                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiHeart aria-hidden="true" />
                    Listening to What Happens Between People
                  </h2>
                  <p>
                    These days I meet couples, individuals, and families at my clinic in Ashdod and online. I keep returning to the moment when a conversation reaches the same familiar dead end — and to the possibility of pausing, listening differently, and finding one small step that may change its direction.
                  </p>
                  <p>
                    I am thinking a great deal about the tension between wanting to solve things quickly and making room for what has not yet been said. For me, this question sits at the heart of couples work, parenting, and mediation.
                  </p>
                </section>

                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiUsers aria-hidden="true" />
                    Parenting in Real Life
                  </h2>
                  <p>
                    I continue to learn from parents living with overload, ADHD, high sensitivity, giftedness, and family transitions. My focus now is translating big ideas into steps that can actually be tried at home — on busy days, without perfect answers, and while remembering that each child needs something a little different.
                  </p>
                </section>

                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiCompass aria-hidden="true" />
                    Meeting in Community
                  </h2>
                  <p>
                    In talks and workshops in Ashdod and elsewhere, I keep asking how to create a conversation that helps people not only receive knowledge but also recognize themselves in it. Group meetings remind me how relieving it can be to discover that we are not the only ones facing a particular difficulty.
                  </p>
                </section>

                <section className={styles.section}>
                  <h2 className={styles.sectionTitle}>
                    <FiBookOpen aria-hidden="true" />
                    Writing, Learning & Building Tools
                  </h2>
                  <p>
                    I collect questions that recur in the room and in the community, then gradually turn them into practical articles and guides. Alongside writing, I am exploring how research and digital tools can make knowledge more accessible without flattening its human complexity. I am especially interested now in writing that is both precise and useful in everyday life.
                  </p>
                </section>

                <div className={`${styles.callout} ${styles.calloutEn}`}>
                  <p>What is a Now Page?</p>
                  <small>
                    This is a snapshot, not a list of services. It was inspired by Derek Sivers&apos; Now Page idea: what I would tell a friend I had not seen for a year. Learn more at <a href="https://nownownow.com/about" target="_blank" rel="noopener noreferrer">nownownow.com</a>.
                  </small>
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
