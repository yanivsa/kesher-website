import React from 'react';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import LeadMagnet from '../../../components/LeadMagnet/LeadMagnet';
import { FiTarget, FiZap, FiSmile, FiCompass } from 'react-icons/fi';
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
        "name": SITE_CONFIG.brand,
        "address": {
          "@type": "PostalAddress",
          "addressLocality": "אשדוד",
          "addressCountry": "IL"
        }
      },
      "description": "הדרכת הורים מקצועית באשדוד. התמחות בילדים עם ADHD, הצבת גבולות ושיפור האווירה המשפחתית."
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
        title="הדרכת הורים באשדוד | ADHD | שירה סהרוני" 
        description="הדרכת הורים מקצועית באשדוד. התמחות בילדים עם ADHD, הצבת גבולות ושיפור האווירה המשפחתית." 
        image="https://images.unsplash.com/photo-1510906594845-bc082582c8cc?auto=format&fit=crop&w=1200&q=80"
      />
      <SchemaOrg data={schemaData} />
      
      <header className={styles.header}>
        <div className={`container ${styles.heroContainer}`}>
          <div className={styles.heroContent}>
            <div className={styles.badge}>מומחית ב-ADHD ואתגרי קשב</div>
            <h1>להפסיק להילחם <br /><span>ולהתחיל להוביל</span></h1>
            <p className={styles.subtitle}>הדרכת הורים מעשית שנותנת לכם ביטחון, סמכות וחיבור אמיתי לילד.</p>
            <a href="https://wa.me/972525267848" className={styles.ctaBtn}>תיאום שיחת היכרות</a>
          </div>
          <div className={styles.heroImageWrapper}>
            <img src="https://images.unsplash.com/photo-1510906594845-bc082582c8cc?auto=format&fit=crop&w=1200&q=80" alt="הדרכת הורים באשדוד" />
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
              <p>אני איתכם לאורך הדרך, מדייקים את הכלים ורואים תוצאות בשטח.</p>
            </div>
          </div>
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
