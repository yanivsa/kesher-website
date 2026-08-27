import React from 'react';
import { FiPlayCircle, FiCalendar, FiMapPin, FiExternalLink } from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './LecturesPage.module.css';

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebPage",
      "@id": `${SITE_CONFIG.url}/lectures`,
      "url": `${SITE_CONFIG.url}/lectures`,
      "name": `הרצאות וסדנאות | ${SITE_CONFIG.title}`,
      "description": "הרצאות וסדנאות מקצועיות מאת שירה סהרוני בנושאי הדרכת הורים, זוגיות והפרעות קשב וריכוז (ADHD).",
      "inLanguage": "he-IL"
    }
  ]
};

const LecturesPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags 
        title="הרצאות וסדנאות" 
        description="צפו בהרצאות וסדנאות מאת שירה סהרוני. הרצאות מקצועיות ומעשירות בנושאי הדרכת הורים, זוגיות והתמודדות עם ADHD." 
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.header}>
        <div className="container">
          <h1 className={styles.title}>הרצאות וסדנאות</h1>
          <p className={styles.subtitle}>
            מגוון הרצאות בנושאי הורות, זוגיות, הפרעות קשב וריכוז (ADHD) והתפתחות משפחתית
          </p>
        </div>
      </header>

      <section className={styles.content}>
        <div className="container">
          <div className={styles.lecturesGrid}>
            
            {/* Lecture 1: Mahut Ashdod - ADHD */}
            <article className={styles.lectureCard}>
              <div className={styles.videoContainer}>
                <video 
                  controls 
                  preload="metadata" 
                  className={styles.videoPlayer}
                  poster="/images/shira_ashdod_poster.jpg"
                >
                  <source src="/videos/shira_mahut_ashdod.mp4" type="video/mp4" />
                  הדפדפן שלך אינו תומך בהצגת וידאו.
                </video>
              </div>
              <div className={styles.lectureContent}>
                <span className={styles.tag}>הדרכת הורים ו-ADHD</span>
                <h2 className={styles.lectureTitle}>הורים כזרקור ומגדלור: לגדל ילד עם ADHD</h2>
                <div className={styles.metaInfo}>
                  <div className={styles.metaItem}>
                    <FiMapPin aria-hidden="true" />
                    <span>מהו"ת אשדוד - המרכז להורות משמעותית</span>
                  </div>
                </div>
                <p className={styles.description}>
                  בהרצאה מרתקת זו במרכז מהו"ת, שירה סהרוני מדברת על הפרעת קשב וריכוז כיתרון וכוח מניע.
                  היא מסבירה כיצד אישים דגולים בהיסטוריה הפכו את אתגרי ה-ADHD להישגים עצומים,
                  וכיצד תפקידנו כהורים להיות עבור ילדינו ה"זרקור" שמאיר את החוזקות, וה"מגדלור" שמכוון אל מול האתגרים בסערות החיים.
                </p>
              </div>
            </article>

            {/* Lecture 2: Parenting Guidance & Family Resilience */}
            <article className={styles.lectureCard}>
              <div className={styles.videoContainer}>
                <video 
                  controls 
                  preload="metadata" 
                  className={styles.videoPlayer}
                  poster="/images/shira_revava_poster.jpg"
                >
                  <source src="/videos/shira_revava.mp4" type="video/mp4" />
                  הדפדפן שלך אינו תומך בהצגת וידאו.
                </video>
              </div>
              <div className={styles.lectureContent}>
                <span className={styles.tag}>הדרכת הורים וחוסן משפחתי</span>
                <h2 className={styles.lectureTitle}>להיות מגדלור בעת סערה: הנחיית הורים וחוסן משפחתי</h2>
                <div className={styles.metaInfo}>
                  <div className={styles.metaItem}>
                    <FiMapPin aria-hidden="true" />
                    <span>הדרכה מקצועית למנחי הורים</span>
                  </div>
                </div>
                <p className={styles.description}>
                  שירה סהרוני מציגה את מהות השליחות של הנחיית הורים: היכולת לתת מענה, ביטחון וכלים מעשיים למשפחות בעתות שגרה ומשבר.
                  דגש מיוחד על תפקיד ההורים כעוגן יציב המאפשר לילדים לצמוח מתוך אתגרים בביטחון, הכלה וחסד.
                </p>
              </div>
            </article>

            {/* Lecture 3: Y.N.R Revava */}
            <article className={styles.lectureCard}>
              <div className={styles.facebookEmbedContainer}>
                <iframe 
                  src="https://www.facebook.com/plugins/post.php?href=https%3A%2F%2Fwww.facebook.com%2Fynrcollege%2Fposts%2F7033553070047976&show_text=true&width=500" 
                  width="100%" 
                  height="450" 
                  style={{ border: 'none', overflow: 'hidden', borderRadius: '8px' }} 
                  scrolling="no" 
                  frameBorder="0" 
                  allowFullScreen={true} 
                  allow="autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share"
                  title="הרצאה בי.נ.ר"
                ></iframe>
              </div>
              <div className={styles.lectureContent}>
                <span className={styles.tag}>רווקות מאוחרת וייעוץ זוגי</span>
                <h2 className={styles.lectureTitle}>נשארתי לבד - על התסכול ותחושת הבדידות ברווקות מאוחרת</h2>
                <div className={styles.metaInfo}>
                  <div className={styles.metaItem}>
                    <FiMapPin aria-hidden="true" />
                    <span>מדרשת רבבה - המדרשה להעצמה (מכללת י.נ.ר)</span>
                  </div>
                  <div className={styles.metaItem}>
                    <FiCalendar aria-hidden="true" />
                    <span>כ"ח אדר א' (תשפ"ב)</span>
                  </div>
                </div>
                <p className={styles.description}>
                  הרצאה מקצועית מאת שירה סהרוני (עו"ד ומגשרת, מומחית בייעוץ זוגי) שניתנה במסגרת לוח הזמנים של "מדרשת רבבה" – המדרשה להעצמה אישית, זוגית ומשפחתית. ההרצאה עסקה בהתמודדות הרגשית, התסכול, ותחושת הבדידות המלווים את תקופת הרווקות המאוחרת, תוך מתן כלים מקצועיים מהשטח.
                </p>
                <a href="https://www.facebook.com/ynrcollege/posts/7033553070047976" target="_blank" rel="noopener noreferrer" className={styles.externalLink}>
                  <FiExternalLink aria-hidden="true" />
                  צפייה בפוסט המלא בפייסבוק
                </a>
              </div>
            </article>

          </div>
        </div>
      </section>
    </div>
  );
};

export default LecturesPage;
