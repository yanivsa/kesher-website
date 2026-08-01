import React from 'react';
import { Link } from 'react-router-dom';
import { FiBookOpen, FiCompass, FiHeart, FiMessageCircle, FiUsers } from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './AboutPage.module.css';

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "ProfilePage",
      "dateCreated": "2024-01-01",
      "dateModified": "2026-07-23",
      "mainEntity": {
        "@type": "Person",
        "name": SITE_CONFIG.author,
        "alternateName": "Shira Saharoni",
        "jobTitle": ["יועצת זוגית", "מנחת הורים", "מגשרת מוסמכת"],
        "description": "שירה סהרוני היא יועצת זוגית, מנחת הורים ומגשרת מוסמכת, עורכת דין בהכשרתה, המלווה זוגות ומשפחות באשדוד ובאונליין.",
        "url": `${SITE_CONFIG.url}/about`,
        "image": `${SITE_CONFIG.url}/images/shira-saharoni.webp`,
        "knowsAbout": [
          "ייעוץ זוגי",
          "גישור",
          "הנחיית הורים",
          "ילדים מחוננים",
          "ADHD",
          "מעברים חינוכיים",
          "משפחות עולים ותושבים חוזרים",
          "זוגיות בעלייה וברילוקיישן",
          "הכנה לנישואים והשנה הראשונה"
        ],
        "worksFor": {
          "@type": "LocalBusiness",
          "@id": `${SITE_CONFIG.url}/#business`,
          "name": SITE_CONFIG.brand
        }
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
          "name": "אודות",
          "item": `${SITE_CONFIG.url}/about`
        }
      ]
    }
  ]
};

const AboutPage: React.FC = () => {

  return (
    <div className={styles.page}>
      <SchemaOrg data={schemaData} />
      <MetaTags 
        title="אודות שירה סהרוני | יועצת זוגית, מנחת הורים ומגשרת"
        description="הכירו את שירה סהרוני — עורכת דין בהכשרתה, מגשרת מוסמכת, יועצת זוגית ומנחת הורים באשדוד ובאונליין."
        image="/images/shira-saharoni.webp"
      />
      <header className={styles.header}>
        <div className="container">
          <span>נעים מאוד</span>
          <h1>אני שירה סהרוני</h1>
          <p>יועצת זוגית, מנחת הורים ומגשרת מוסמכת.</p>
        </div>
      </header>

      <section className={styles.story}>
        <div className={`container ${styles.storyGrid}`}>
          <div className={styles.imageWrapper}>
            <img
              src="/images/shira-saharoni.webp"
              alt="שירה סהרוני, יועצת זוגית ומשפחתית, מגשרת ומנחת הורים"
              width="1271"
              height="1280"
              fetchPriority="high"
            />
            <div className={styles.imageBadge}>מקשיבים • מבינים • מתקדמים</div>
          </div>
          <div className={styles.storyContent}>
            <span className={styles.eyebrow}>הדרך המקצועית שלי</span>
            <h2>מעולם המשפט לעולמות ההנחיה, הייעוץ והחינוך</h2>
            <p className={styles.lead}>
              אני עורכת דין בהכשרתי ומגשרת מוסמכת, שבחרה להפנות את היכולת לנתח מצבים מורכבים, להקשיב לכל הצדדים ולבנות הסכמות — לעבודה עם זוגות, הורים ומשפחות.
            </p>
            <p>
              לאורך הדרך גיליתי שהכלים האלה משמעותיים במיוחד ברגעים היומיומיים שבהם קשה לדבר, להבין או להתקדם. כיום אני מלווה תהליכים מעשיים ורגישים מתוך ראייה של המשפחה כמערכת אחת: הקשר הזוגי, ההורות, הילדים והמסגרות שסביבם.
            </p>
            <p>
              בעבודה שלי אני משלבת הקשבה, בהירות וכלים שאפשר ליישם בבית. לצד ייעוץ זוגי, גישור והנחיית הורים, אני מעניקה מקום מרכזי למשפחות לילדים מחוננים, לילדים עם ADHD, למעברים חינוכיים ולמשפחות בתהליך עלייה או חזרה לישראל.
            </p>
          </div>
        </div>
      </section>

      <section className={styles.values}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>מה אני מביאה לחדר?</h2>
            <p>לא פתרון מוכן מראש, אלא דרך מקצועית ומכבדת להבין את התמונה ולבנות שינוי שמתאים לחיים שלכם.</p>
          </div>
          <div className={styles.valuesGrid}>
            <article>
              <FiMessageCircle aria-hidden="true" />
              <h3>הקשבה לכל הקולות</h3>
              <p>מרחב שבו אפשר לומר גם את הדברים שקשה לנסח, בלי לוותר על הכבוד ועל הקשר.</p>
            </article>
            <article>
              <FiCompass aria-hidden="true" />
              <h3>ראייה מערכתית</h3>
              <p>הבנה של החיבור בין הזוגיות, ההורות, הילד, המסגרת והשינויים שהמשפחה עוברת.</p>
            </article>
            <article>
              <FiBookOpen aria-hidden="true" />
              <h3>כלים מעשיים</h3>
              <p>צעדים שאפשר לתרגל בין המפגשים ולבחון בתוך השגרה האמיתית של הבית.</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.focus}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>תחומי הליווי</h2>
            <p>אפשר להתחיל מהנושא שמעסיק אתכם עכשיו, ובהמשך לחבר בין החלקים השונים של התמונה המשפחתית.</p>
          </div>
          <div className={styles.focusGrid}>
            <Link to="/services/couples">
              <FiHeart aria-hidden="true" />
              <strong>ייעוץ זוגי</strong>
              <span>תקשורת, קירבה, אמון והכנה לחיים משותפים.</span>
            </Link>
            <Link to="/services/premarital-first-year">
              <FiHeart aria-hidden="true" />
              <strong>הכנה לנישואים והשנה הראשונה</strong>
              <span>כסף, בית, משפחות, תקשורת והסכמות לחיים המשותפים.</span>
            </Link>
            <Link to="/services/couples-aliyah-relocation">
              <FiCompass aria-hidden="true" />
              <strong>זוגיות בעלייה וברילוקיישן</strong>
              <span>תפקידים, הסתגלות ושייכות לפני מעבר מדינה, במהלכו ואחריו.</span>
            </Link>
            <Link to="/services/late-singleness">
              <FiHeart aria-hidden="true" />
              <strong>ייעוץ ברווקות מאוחרת</strong>
              <span>שחיקה, לחץ מהסביבה, בדידות ודפוסים חוזרים.</span>
            </Link>
            <Link to="/services/finding-relationship">
              <FiMessageCircle aria-hidden="true" />
              <strong>ליווי למציאת זוגיות</strong>
              <span>היכרויות, בחירת קשר, תקשורת והתקדמות לזוגיות.</span>
            </Link>
            <Link to="/services/mediation">
              <FiCompass aria-hidden="true" />
              <strong>גישור</strong>
              <span>בירור צרכים ובניית הסכמות מכבדות וישימות.</span>
            </Link>
            <Link to="/services/parenting">
              <FiUsers aria-hidden="true" />
              <strong>הנחיית הורים</strong>
              <span>גבולות, שגרה, ADHD, תפקודים ניהוליים ומעברים.</span>
            </Link>
            <Link to="/services/gifted-parenting">
              <FiBookOpen aria-hidden="true" />
              <strong>ילדים מחוננים</strong>
              <span>רגישות, פרפקציוניזם, שייכות והכנה למסגרת.</span>
            </Link>
            <Link to="/services/aliyah-families">
              <FiMessageCircle aria-hidden="true" />
              <strong>עולים ותושבים חוזרים</strong>
              <span>ליווי זוגי והורי בתקופה של הסתגלות ובניית בית.</span>
            </Link>
          </div>
        </div>
      </section>

      <section className={styles.belief}>
        <div className="container">
          <div className={styles.beliefContent}>
            <h2>האני המאמין שלי</h2>
            <p>
              שינוי אינו מתחיל כשמישהו במשפחה „מתוקן”. הוא מתחיל כשאפשר להבין את הדפוס, לדבר אחרת ולבחור צעד קטן שאפשר לעמוד בו.
            </p>
            <p>
              התפקיד שלי הוא לעזור לכם ליצור בהירות, חיבור ושיתוף פעולה — בין בני זוג, בין הורים לילדים ובין המשפחה למסגרות שסביבה.
            </p>
            <Link to={SITE_CONFIG.links.appointment}>קביעת פגישת ייעוץ</Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default AboutPage;
