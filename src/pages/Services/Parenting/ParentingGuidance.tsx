import React from 'react';
import { Link } from 'react-router-dom';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import LeadMagnet from '../../../components/LeadMagnet/LeadMagnet';
import { FiTarget, FiZap, FiSmile } from 'react-icons/fi';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from './ParentingGuidance.module.css';

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
      "description": "הדרכת הורים מקצועית באשדוד. התמחות בילדים עם ADHD, הכנה לכיתה א', הצבת גבולות ושיפור האווירה המשפחתית.",
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
    }
  ]
};

const ParentingGuidance: React.FC = () => {

  return (
    <div className={styles.page}>
      <MetaTags 
        title="הדרכת הורים באשדוד | ADHD והכנה לכיתה א' | שירה סהרוני"
        description="הדרכת הורים מקצועית באשדוד. התמחות בהכנה לכיתה א' לילדים עם ADHD, בניית שגרה, ויסות רגשי והצבת גבולות."
        image="/images/generated/services/parenting-room.jpg"
      />
      <SchemaOrg data={schemaData} />
      
      <header className={styles.header}>
        <div className={`container ${styles.heroContainer}`}>
          <div className={styles.heroContent}>
            <div className={styles.badge}>ליווי הורים סביב ADHD ואתגרי קשב</div>
            <h1>להפסיק להילחם <br /><span>ולהתחיל להוביל</span></h1>
            <p className={styles.subtitle}>הדרכת הורים מעשית שנותנת לכם ביטחון, סמכות וחיבור אמיתי לילד.</p>
            <a href="https://wa.me/972502763802" className={styles.ctaBtn}>תיאום שיחת היכרות</a>
          </div>
          <div className={styles.heroImageWrapper}>
            <img src="/images/generated/services/parenting-room.jpg" alt="מרחב נעים להדרכת הורים" width="1600" height="900" />
          </div>
        </div>
      </header>

      <section className={styles.segments}>
        <div className="container">
          <div className={styles.segmentGrid}>
            <div className={styles.segment}>
              <FiZap className={styles.icon} />
              <h3>התמחות ב-ADHD</h3>
              <p>הבנת המוח של ילד הקשב היא המפתח. נלמד איך 'להפעיל' אותו נכון, איך למנוע התפרצויות ואיך לשמור על הדימוי העצמי שלו.</p>
            </div>
            <div className={styles.segment}>
              <FiTarget className={styles.icon} />
              <h3>גבולות ללא מלחמות</h3>
              <p>איך להציב גבולות ברורים ועקביים בלי להרים את הקול ובלי להרגיש אשמה בסוף היום.</p>
            </div>
            <div className={styles.segment}>
              <FiSmile className={styles.icon} />
              <h3>החזרת ההנאה לבית</h3>
              <p>נהפוך את הבית למקום רגוע שנעים להיות בו, ונגלה מחדש את רגעי הקרבה עם הילדים.</p>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.howItWorks}>
        <div className="container">
          <h2>איך נראה ליווי הורי אצלי?</h2>
          <div className={styles.processSteps}>
            <div className={styles.step}>
              <div className={styles.stepNum}>01</div>
              <h4>ניתוח הדינמיקה</h4>
              <p>נבין מה באמת קורה בבית - איפה הקושי ומה מעורר את מאבקי הכוח.</p>
            </div>
            <div className={styles.step}>
              <div className={styles.stepNum}>02</div>
              <h4>בניית אסטרטגיה</h4>
              <p>תקבלו כלים מותאמים אישית למוח של הילד שלכם ולסגנון ההורי שלכם.</p>
            </div>
            <div className={styles.step}>
              <div className={styles.stepNum}>03</div>
              <h4>ליווי ויישום</h4>
              <p>אני איתכם לאורך הדרך, מדייקים את הכלים ובודקים מה עוזר בבית.</p>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.specialization}>
        <div className="container">
          <div className={styles.specializationIntro}>
            <span>תחום התמחות</span>
            <h2>הכנה לכיתה א' לילדים עם ADHD</h2>
            <p>
              המעבר מהגן לבית הספר דורש מילדי קשב הרבה יותר מידע של אותיות ומספרים. בליווי ממוקד נבנה יחד שגרת בוקר,
              הרגלי התארגנות, כלים לוויסות רגשי ודרך ברורה לשיתוף פעולה עם המחנכת.
            </p>
          </div>
          <div className={styles.specializationGrid}>
            <article>
              <h3>מוכנות רגשית</h3>
              <p>הפחתת אי-ודאות, הכרות מוקדמת עם המסגרת ותרגול תגובות למצבים חדשים.</p>
            </article>
            <article>
              <h3>שגרה והתארגנות</h3>
              <p>בניית רצף בוקר פשוט, ארגון ילקוט וציוד, וחיזוק עצמאות בלי מאבקי כוח.</p>
            </article>
            <article>
              <h3>שותפות עם בית הספר</h3>
              <p>הצגת הצרכים של הילד באופן חיובי ויצירת תקשורת יעילה עם הצוות החינוכי.</p>
            </article>
          </div>
          <Link to="/blog?category=הדרכת הורים&subcategory=הכנה לכיתה א' ו-ADHD" className={styles.specializationLink}>
            למאמרים על הכנה לכיתה א' ו-ADHD
          </Link>
        </div>
      </section>

      <section className={styles.ctaArea}>
        <div className="container">
          <LeadMagnet />
          <div className={styles.finalCall}>
            <h2>אתם לא חייבים לעשות את זה לבד.</h2>
            <p>בואו נחזיר את הביטחון להורות שלכם.</p>
            <a href="/contact" className={styles.btnPrimary}>לשיחת ייעוץ ראשונה</a>
          </div>
        </div>
      </section>
    </div>
  );
};

export default ParentingGuidance;
