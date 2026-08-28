import React from 'react';
import { Link } from 'react-router-dom';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import LeadMagnet from '../../../components/LeadMagnet/LeadMagnet';
import ServiceFAQ from '../../../components/FAQ/ServiceFAQ';
import TherapistBio from '../../../components/TherapistBio/TherapistBio';
import faqs from '../../../data/faqs';
import { FiMessageCircle, FiShield, FiStar } from 'react-icons/fi';
import { FaWhatsapp } from 'react-icons/fa';
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
      "description": "ייעוץ זוגי ממוקד ומעשי באשדוד ובאונליין לזוגות המתמודדים עם קשיי תקשורת, ריבים חוזרים, משברים ורצון בשיפור הקשר.",
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
        title="ייעוץ זוגי באשדוד ואונליין"
        description="ייעוץ זוגי מקצועי ורגיש באשדוד ובאונליין (Zoom). שיפור תקשורת זוגית, חיזוק האינטימיות, התמודדות עם משברים והכנה לחתונה."
        canonical={`${SITE_CONFIG.url}/services/couples`}
        image="/images/generated/services/couples-room.jpg"
      />
      <SchemaOrg data={schemaData} />
      
      <header className={styles.hero}>
        <div className={`container ${styles.heroContainer}`}>
          <div className={styles.heroContent}>
            <div className={styles.badge}>ייעוץ זוגי באשדוד ובאונליין</div>
            <h1>לדבר על מה שקורה <br /><span>בלי לחזור לאותו ריב</span></h1>
            <p className={styles.subtitle}>פגישה לשני בני הזוג, שבה אפשר להבין את הדפוס שחוזר ולבדוק מה ניתן לשנות.</p>
            <div className={styles.heroActions}>
              <Link to={SITE_CONFIG.links.appointment} className={styles.ctaBtn}>
                קביעת פגישת ייעוץ
              </Link>
              <a
                href={SITE_CONFIG.links.whatsapp}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.whatsappBtn}
              >
                <FaWhatsapp aria-hidden="true" />
                <span>פנייה ב-WhatsApp</span>
              </a>
            </div>
          </div>
          <div className={styles.heroImageWrapper}>
            <img src="/images/generated/services/couples-room.jpg" alt="מרחב שיחה זוגי נעים" width="1600" height="900" fetchPriority="high" />
          </div>
        </div>
      </header>

      <section className={styles.painPoints}>
        <div className="container">
          <h2 className={styles.sectionTitle}>מתי זוגות פונים לייעוץ?</h2>
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
            <p>המטרה אינה להכריע מי צודק. נבדוק איך השיחה מתנהלת, מה כל אחד שומע ברגעים טעונים ומה יעזור לכם להישאר באותה שיחה בלי להסלים או להתרחק.</p>
            <ul className={styles.approachList}>
              <li>זיהוי 'מעגלי המריבה' שלכם וכלים לעצירה בזמן אמת.</li>
              <li>תרגול שפת רגש במקום שפת האשמה.</li>
              <li>יצירת זמן וקביעות לקשר בתוך שגרה עמוסה.</li>
              <li>ליווי רגיש בשיקום אמון אחרי משברים עמוקים.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className={styles.howItWorks}>
        <div className="container">
          <h2>איך נראה ליווי זוגי אצלי?</h2>
          <div className={styles.processSteps}>
            <div className={styles.step}>
              <div className={styles.stepNum}>01</div>
              <h4>ממפים את התמונה</h4>
              <p>נבין את "מעגלי המריבה" שלכם, באילו רגעים קשה במיוחד ואיך כל אחד מגיב כשמתחיל החיכוך.</p>
            </div>
            <div className={styles.step}>
              <div className={styles.stepNum}>02</div>
              <h4>בוחרים שינוי אפשרי</h4>
              <p>נזהה מוקד אחד שאפשר להתחיל ממנו ונבחר תגובה או כלים מעשיים לעצירה והקשבה שאפשר לנסות כבר השבוע.</p>
            </div>
            <div className={styles.step}>
              <div className={styles.stepNum}>03</div>
              <h4>בודקים ומדייקים</h4>
              <p>נבחן בין הפגישות מה עזר בבית, מה עדיין קשה, ונדייק את הדרך עד שנוצרת תחושת ביטחון ושותפות מחודשת.</p>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.boundaries}>
        <div className="container">
          <div className={styles.boundariesContent}>
            <h2>מתי צריך מענה אחר או נוסף?</h2>
            <p>ייעוץ זוגי דורש נכונות של שני הצדדים להשתתף. יש מצבים שבהם נכון להתחיל במענה ייעודי אחר:</p>
            <ul className={styles.boundariesList}>
              <li>כאשר רק צד אחד מעוניין להגיע והשני אינו מסכים להשתתף.</li>
              <li>כאשר המטרה היחידה היא לשנות את בן או בת הזוג, בלי לבחון את הדינמיקה המשותפת.</li>
              <li>במצבים של אלימות או סכנה בבית יש לפנות תחילה למענה ייעודי ומותאם.</li>
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
            <Link to="/services/premarital-first-year">לעמוד המלא על הכנה לנישואים וליווי בשנה הראשונה</Link>
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

      <TherapistBio />

      <section className={styles.ctaSection}>
        <div className="container">
          <LeadMagnet />
          <div className={styles.bottomCta}>
            <h2>אפשר לבדוק אם הייעוץ מתאים לכם</h2>
            <p>הפגישה מתקיימת באשדוד או אונליין ונמשכת 50 דקות.</p>
            <Link to={SITE_CONFIG.links.appointment} className={styles.finalBtn}>בחירת מועד לפגישה</Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default CouplesCounseling;
