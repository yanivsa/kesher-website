import React from 'react';
import { Link } from 'react-router-dom';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import LeadMagnet from '../../../components/LeadMagnet/LeadMagnet';
import ServiceFAQ from '../../../components/FAQ/ServiceFAQ';
import faqs from '../../../data/faqs';
import { FiMessageCircle, FiShield, FiStar } from 'react-icons/fi';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from './CouplesCounseling.module.css';

const couplesFaqs = faqs.filter(f => f.category === "ייעוץ זוגי");

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Service",
      "name": "ייעוץ זוגי",
      "serviceType": "ייעוץ זוגי",
      "url": `${SITE_CONFIG.url}/services/couples`,
      "provider": {
        "@type": "LocalBusiness",
        "@id": `${SITE_CONFIG.url}/#business`
      },
      "description": "הכנה לחתונה לזוגות שרוצים להתחיל נכון, כולל ליווי למתחתנים שהוריהם גרושים ולזוגות שבהם אחד או שני בני הזוג מתמודדים עם ADHD.",
      "image": `${SITE_CONFIG.url}/images/generated/services/couples-room.jpg`
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
          "name": "ייעוץ זוגי",
          "item": `${SITE_CONFIG.url}/services/couples`
        }
      ]
    },
    {
      "@type": "FAQPage",
      "mainEntity": couplesFaqs.map(faq => ({
        "@type": "Question",
        "name": faq.question,
        "acceptedAnswer": {
          "@type": "Answer",
          "text": faq.answer
        }
      }))
    }
  ]
};

const CouplesCounseling: React.FC = () => {

  return (
    <div className={styles.page}>
      <MetaTags 
        title="ייעוץ זוגי באשדוד ואונליין | שירה סהרוני — יועצת זוגית ומנחת הורים"
        description="ייעוץ זוגי מקצועי ורגיש באשדוד ובאונליין (Zoom). שיפור תקשורת זוגית, חיזוק האינטימיות, התמודדות עם משברים והכנה לחתונה."
        image="/images/generated/services/couples-room.jpg"
      />
      <SchemaOrg data={schemaData} />
      
      <header className={styles.hero}>
        <div className={`container ${styles.heroContainer}`}>
          <div className={styles.heroContent}>
            <div className={styles.badge}>מרחב בטוח לזוגיות שלכם</div>
            <h1>להחזיר את <br /><span>החברות והאינטימיות</span></h1>
            <p className={styles.subtitle}>ייעוץ זוגי רגיש ומעשי שמתמקד בתקשורת, אמון וחיבור.</p>
            <a href={SITE_CONFIG.links.whatsapp} className={styles.ctaBtn}>תיאום שיחת היכרות</a>
          </div>
          <div className={styles.heroImageWrapper}>
            <img src="/images/generated/services/couples-room.jpg" alt="מרחב שיחה זוגי נעים" width="1600" height="900" fetchPriority="high" />
          </div>
        </div>
      </header>

      <section className={styles.painPoints}>
        <div className="container">
          <h2 className={styles.sectionTitle}>מרגישים שאתם בלופ?</h2>
          <div className={styles.grid}>
            <div className={styles.card}>
              <FiMessageCircle className={styles.icon} />
              <h3>התקשורת תקועה</h3>
              <p>כל ניסיון לדבר הופך למריבה או לשתיקה כואבת. אתם כבר לא יודעים איך להביע צורך בלי להאשים.</p>
            </div>
            <div className={styles.card}>
              <FiStar className={styles.icon} />
              <h3>האינטימיות נעלמה</h3>
              <p>מרגישים כמו 'שותפים לדירה' שמנהלים לוגיסטיקה וילדים, אבל שכחתם איך להיות פשוט זוג.</p>
            </div>
            <div className={styles.card}>
              <FiShield className={styles.icon} />
              <h3>משבר אמון</h3>
              <p>התמודדות עם בגידה, הסתרות או שחיקה מצטברת שגרמה לכם להפסיק להאמין שאפשר אחרת.</p>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.approach}>
        <div className="container">
          <div className={styles.approachContent}>
            <h2>איך אני עוזרת לכם?</h2>
            <p>הגישה שלי לא מחפשת 'מי צודק'. אנחנו נתמקד ב'איך' - איך אתם מתקשרים, איך אתם חווים אחד את השני, ואיך בונים בסיס בטוח של אמון וחברות.</p>
            <ul className={styles.approachList}>
              <li>זיהוי 'מעגלי המריבה' שלכם וכלים לעצירה בזמן אמת.</li>
              <li>תרגול שפת רגש במקום שפת האשמה.</li>
              <li>בניית טקסים של קרבה וחיבור בתוך השגרה המלחיצה.</li>
              <li>ליווי רגיש בשיקום אמון אחרי משברים עמוקים.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className={styles.boundaries}>
        <div className="container">
          <div className={styles.boundariesContent}>
            <h2>למי הליווי פחות יתאים?</h2>
            <p>כדי שהתהליך יצליח, נדרשת בשלות ומחויבות. הליווי פחות מתאים במקרים הבאים:</p>
            <ul className={styles.boundariesList}>
              <li>מחפשים 'קסמים' או פתרונות אינסטנט בלי נכונות לעבודת עומק.</li>
              <li>מגיעים כדי 'לתקן את בן/בת הזוג' בלי רצון להסתכל גם על החלק שלכם בדינמיקה.</li>
              <li>מצבי אלימות במשפחה (במקרים אלו יש לפנות למרכזים ייעודיים לטיפול באלימות).</li>
            </ul>
          </div>
        </div>
      </section>

      <section className={styles.specializations}>
        <div className="container">
          <div className={styles.specializationsHeader}>
            <span>תחום התמחות מרכזי</span>
            <h2>הכנה לחתונה לזוגות שרוצים להתחיל נכון</h2>
            <p>תהליך ממוקד לבניית שפה זוגית, הסכמות וכלים מעשיים לפני החתונה. בתוך התהליך ניתן מקום מיוחד לסיפורי המשפחה ולדרך שבה ADHD משפיע על הקשר.</p>
          </div>
          <div className={styles.specializationsGrid}>
            <article className={styles.specializationCard}>
              <h3>מתחתנים כשההורים גרושים</h3>
              <p>
                נותנים מקום לחששות, לנאמנויות משפחתיות ולדפוסים שנלמדו בבית, בלי להפוך את הסיפור של ההורים לנבואה.
                בונים יחד דרך חדשה לניהול מחלוקות, גבולות וקשר עם משפחות המוצא.
              </p>
              <Link to="/blog?category=זוגיות&subcategory=הכנה לחתונה">למאמרים על הכנה לחתונה</Link>
            </article>
            <article className={styles.specializationCard}>
              <h3>זוגות שמתמודדים עם ADHD</h3>
              <p>
                כאשר אחד או שני בני הזוג מתמודדים עם ADHD, מכינים מראש כללים שמתאימים לניהול זמן, משימות, עומס ותקשורת.
                המטרה היא להתחיל את החיים המשותפים כשותפים, בלי שאחד יהפוך למנהל של השני.
              </p>
              <Link to="/blog?category=זוגיות&subcategory=הכנה לחתונה">למאמרים על הכנה לחתונה ו-ADHD</Link>
            </article>
          </div>
        </div>
      </section>

      <ServiceFAQ category="ייעוץ זוגי" />

      <section className={styles.ctaSection}>
        <div className="container">
          <LeadMagnet />
          <div className={styles.bottomCta}>
            <h2>מגיע לכם להרגיש שוב בבית בתוך הקשר.</h2>
            <p>אני כאן באשדוד (ובאונליין) כדי ללוות אתכם צעד אחר צעד.</p>
            <a href="/contact" className={styles.finalBtn}>בואו נתחיל לדבר</a>
          </div>
        </div>
      </section>
    </div>
  );
};

export default CouplesCounseling;
