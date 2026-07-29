import React from 'react';
import { Link } from 'react-router-dom';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import LeadMagnet from '../../../components/LeadMagnet/LeadMagnet';
import ServiceFAQ from '../../../components/FAQ/ServiceFAQ';
import faqs from '../../../data/faqs';
import { FiTarget, FiZap, FiSmile } from 'react-icons/fi';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from './ParentingGuidance.module.css';

const parentingFaqs = faqs.filter(f => f.category === "הדרכת הורים");

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Service",
      "name": "הדרכת הורים",
      "serviceType": "הדרכת הורים",
      "url": `${SITE_CONFIG.url}/services/parenting`,
      "provider": {
        "@type": "LocalBusiness",
        "@id": `${SITE_CONFIG.url}/#business`
      },
      "description": "הדרכת הורים באשדוד ובאונליין לילדים מחוננים, לילדים עם ADHD ולמשפחות המתכוננות לכיתה א' ולמעברים חינוכיים.",
      "image": `${SITE_CONFIG.url}/images/generated/services/parenting-room.jpg`
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
          "name": "הדרכת הורים",
          "item": `${SITE_CONFIG.url}/services/parenting`
        }
      ]
    },
    {
      "@type": "FAQPage",
      "mainEntity": parentingFaqs.map(faq => ({
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

const ParentingGuidance: React.FC = () => {

  return (
    <div className={styles.page}>
      <MetaTags 
        title="הדרכת הורים | מחוננים, ADHD והכנה לכיתה א'"
        description="הדרכת הורים באשדוד ובאונליין לילדים מחוננים, לילדים עם ADHD ולהכנה לכיתה א' דרך תפקודים ניהוליים, ויסות ועצמאות."
        image="/images/generated/services/parenting-room.jpg"
      />
      <SchemaOrg data={schemaData} />
      
      <header className={styles.header}>
        <div className={`container ${styles.heroContainer}`}>
          <div className={styles.heroContent}>
            <div className={styles.badge}>מחוננים • ADHD • מעברים חינוכיים</div>
            <h1>להבין מה מקשה בבית <br /><span>ולבחור תגובה שעוזרת</span></h1>
            <p className={styles.subtitle}>הדרכת הורים שמחברת בין הצרכים של הילד, הגבולות בבית ומה שאפשר ליישם בשגרה שלכם.</p>
            <Link to={SITE_CONFIG.links.appointment} className={styles.ctaBtn}>קביעת פגישת ייעוץ</Link>
          </div>
          <div className={styles.heroImageWrapper}>
            <img src="/images/generated/services/parenting-room.jpg" alt="מרחב נעים להדרכת הורים" width="1600" height="900" fetchPriority="high" />
          </div>
        </div>
      </header>

      <section className={styles.segments}>
        <div className="container">
          <div className={styles.segmentGrid}>
            <div className={styles.segment}>
              <FiZap className={styles.icon} />
              <h3>ADHD ואתגרי קשב</h3>
              <p>נבין מה מקשה על הילד להתארגן, לווסת ולהתמיד, ונבנה תמיכה שמחזקת עצמאות ושומרת על הדימוי העצמי.</p>
            </div>
            <div className={styles.segment}>
              <FiTarget className={styles.icon} />
              <h3>גבולות עם פחות חיכוכים</h3>
              <p>איך להציב גבולות ברורים ועקביים מתוך סמכות שקטה, ולהפחית את רגשות האשמה בסוף היום.</p>
            </div>
            <div className={styles.segment}>
              <FiSmile className={styles.icon} />
              <h3>יותר רגעים של שיתוף פעולה</h3>
              <p>נחפש שינויים קטנים שמפחיתים חיכוך ומאפשרים גם קשר, משחק ושיחה בתוך היום העמוס.</p>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.giftedCallout}>
        <div className="container">
          <div className={styles.giftedContent}>
            <span>תחום ליווי מרכזי</span>
            <h2>הנחיית הורים לילדים מחוננים</h2>
            <p>
              יכולת גבוהה יכולה להגיע לצד רגישות, פרפקציוניזם, שעמום, קושי חברתי או פער בין ההבנה של הילד לבין יכולת ההתארגנות והוויסות שלו. הליווי מחבר בין הצרכים של הילד, ההורות והמסגרת החינוכית.
            </p>
            <Link to="/services/gifted-parenting">לעמוד המלא על הורים לילדים מחוננים</Link>
          </div>
        </div>
      </section>

      <section className={styles.howItWorks}>
        <div className="container">
          <h2>איך נראה ליווי הורי אצלי?</h2>
          <div className={styles.processSteps}>
            <div className={styles.step}>
              <div className={styles.stepNum}>01</div>
              <h4>מכירים את השגרה</h4>
              <p>נבין באילו רגעים קשה במיוחד, מה קורה לפני העימות ואיך כל אחד מגיב.</p>
            </div>
            <div className={styles.step}>
              <div className={styles.stepNum}>02</div>
              <h4>בוחרים שינוי אחד</h4>
              <p>נבחר תגובה או הרגל שמתאימים לגיל הילד ולמציאות בבית, ונגדיר איך לנסות אותם.</p>
            </div>
            <div className={styles.step}>
              <div className={styles.stepNum}>03</div>
              <h4>בודקים ומדייקים</h4>
              <p>בפגישה הבאה נבדוק מה עזר, מה לא היה ישים ומה כדאי לשנות.</p>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.boundaries}>
        <div className="container">
          <div className={styles.boundariesContent}>
            <h2>מתי כדאי לשלב גורם מקצועי נוסף?</h2>
            <p>הדרכת הורים אינה מחליפה אבחון או טיפול בילד. לפעמים נכון לשלב אותה עם מענה נוסף:</p>
            <ul className={styles.boundariesList}>
              <li>כאשר עולה צורך בבירור התפתחותי, רגשי, לימודי או רפואי.</li>
              <li>כאשר הילד או ההורים נמצאים במצוקה שדורשת טיפול ישיר ומותאם.</li>
            </ul>
          </div>
        </div>
      </section>

      <section className={styles.specialization}>
        <div className="container">
          <div className={styles.specializationIntro}>
            <span>תחום התמחות</span>
            <h2>הכנה לכיתה א' דרך בניית תפקודים ניהוליים</h2>
            <p>
              המעבר מהגן לבית הספר דורש יותר מהיכרות עם אותיות ומספרים. לילדים עם ADHD ולכל ילד שזקוק לכך נבנה יחד שגרת בוקר,
              הרגלי התארגנות, מעבר בין משימות, כלים לוויסות רגשי ודרך ברורה לשיתוף פעולה עם הצוות החינוכי.
            </p>
            <p>
              זהו תהליך משותף לילד ולהוריו: הילד מתרגל מיומנויות ועצמאות, וההורים בונים סביבת תמיכה עקבית שאפשר לקיים לאורך זמן.
            </p>
          </div>
          <div className={styles.specializationGrid}>
            <article>
              <h3>מוכנות רגשית</h3>
              <p>הפחתת אי-ודאות, הכרות מוקדמת עם המסגרת ותרגול תגובות למצבים חדשים.</p>
            </article>
            <article>
              <h3>תפקודים ניהוליים</h3>
              <p>בניית רצף בוקר, ארגון ילקוט וציוד, מעבר בין משימות, התמודדות עם הסחות וחיזוק עצמאות.</p>
            </article>
            <article>
              <h3>שותפות עם בית הספר</h3>
              <p>הצגת הצרכים של הילד באופן חיובי ויצירת תקשורת יעילה עם הצוות החינוכי.</p>
            </article>
          </div>
          <Link to="/blog?category=הדרכת הורים&subcategory=הכנה לכיתה א' ו-ADHD" className={styles.specializationLink}>
            למאמרים על הכנה לכיתה א', תפקודים ניהוליים ו-ADHD
          </Link>
        </div>
      </section>

      <ServiceFAQ category="הדרכת הורים" />

      <section className={styles.ctaArea}>
        <div className="container">
          <LeadMagnet />
          <div className={styles.finalCall}>
            <h2>אפשר להתחיל ממה שקורה אצלכם השבוע</h2>
            <p>הפגישה הראשונה נועדה להבין את התמונה ולבחור מוקד מעשי להמשך.</p>
            <Link to={SITE_CONFIG.links.appointment} className={styles.btnPrimary}>בחירת מועד לפגישה</Link>
          </div>
        </div>
      </section>
    </div>
  );
};

export default ParentingGuidance;
