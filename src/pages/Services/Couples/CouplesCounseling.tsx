import React from 'react';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import LeadMagnet from '../../../components/LeadMagnet/LeadMagnet';
import { FiHeart, FiMessageCircle, FiShield, FiStar } from 'react-icons/fi';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from './CouplesCounseling.module.css';

const CouplesCounseling: React.FC = () => {
  const schemaData = {
    "@context": "https://schema.org",
    "@type": "Service",
    "serviceType": "ייעוץ זוגי",
    "provider": {
      "@type": "LocalBusiness",
      "name": SITE_CONFIG.brand,
      "address": {
        "@type": "PostalAddress",
        "addressLocality": "אשדוד",
        "addressCountry": "IL"
      }
    },
    "description": "ייעוץ זוגי מקצועי ורגיש באשדוד. בואו לשפר את התקשורת, לפתור קונפליקטים ולהחזיר את האינטימיות לקשר."
  };

  return (
    <div className={styles.page}>
      <MetaTags 
        title="ייעוץ זוגי באשדוד | שירה סהרוני" 
        description="ייעוץ זוגי מקצועי ורגיש באשדוד. בואו לשפר את התקשורת, לפתור קונפליקטים ולהחזיר את האינטימיות לקשר." 
      />
      <SchemaOrg data={schemaData} />
      
      <header className={styles.hero}>
        <div className={`container ${styles.heroContainer}`}>
          <div className={styles.heroContent}>
            <div className={styles.badge}>מרחב בטוח לזוגיות שלכם</div>
            <h1>להחזיר את <br /><span>החברות והאינטימיות</span></h1>
            <p className={styles.subtitle}>ייעוץ זוגי רגיש ומקצועי המשלב כלים מעולם ה-Gottman וה-EFT.</p>
            <a href="https://wa.me/972525267848" className={styles.ctaBtn}>תיאום שיחת היכרות</a>
          </div>
          <div className={styles.heroImageWrapper}>
            <img src="https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?auto=format&fit=crop&w=1200&q=80" alt="ייעוץ זוגי באשדוד" />
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
