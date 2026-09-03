import React from 'react';
import { FiCalendar, FiMapPin, FiExternalLink, FiVideo, FiCamera, FiPhone, FiMessageCircle } from 'react-icons/fi';
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

      {/* Header Hero */}
      <header className={styles.header}>
        <div className="container">
          <span className={styles.eyebrow}>הרצאות, סדנאות והדרכות</span>
          <h1 className={styles.title}>הרצאות וסדנאות</h1>
          <p className={styles.subtitle}>
            מגוון הרצאות בנושאי הורות, זוגיות, הפרעות קשב וריכוז (ADHD) והתפתחות משפחתית
          </p>
          <div className={styles.headerBadges}>
            <span className={styles.headerBadge}>כלים מעשיים וישימים</span>
            <span className={styles.headerBadge}>שילוב ידע מקצועי והומור</span>
            <span className={styles.headerBadge}>התאמה אישית לארגונים וקהילות</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <section className={styles.content}>
        <div className="container">
          
          <div className={styles.sectionHeading}>
            <h2 className={styles.sectionTitle}>הרצאות מוקלטות ותיעודים מהשטח</h2>
            <p className={styles.sectionSubtitle}>
              טעימה מתוך מגוון ההרצאות והסדנאות ששירה מעבירה ברחבי הארץ
            </p>
          </div>

          <div className={styles.lecturesGrid}>
            
            {/* Lecture 1: Mahut Ashdod - ADHD */}
            <article className={styles.lectureCard}>
              <div className={styles.mediaContainer}>
                <div className={styles.mediaBadge}>
                  <FiVideo aria-hidden="true" />
                  <span>הרצאת וידאו</span>
                </div>
                <video 
                  controls 
                  preload="metadata" 
                  className={styles.videoPlayer}
                  poster="/images/lectures/shira_lecture_ashdod_podium.jpg"
                >
                  <source src="/videos/shira_mahut_ashdod.mp4" type="video/mp4" />
                  הדפדפן שלך אינו תומך בהצגת וידאו.
                </video>
              </div>
              <div className={styles.lectureContent}>
                <div className={styles.cardHeader}>
                  <span className={styles.tag}>הדרכת הורים ו-ADHD</span>
                </div>
                <h3 className={styles.lectureTitle}>הורים כזרקור ומגדלור: לגדל ילד עם ADHD</h3>
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
                <div className={styles.cardFooter}>
                  <a 
                    href={SITE_CONFIG.links.whatsapp}
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className={styles.cardActionLink}
                  >
                    <FiMessageCircle aria-hidden="true" />
                    <span>הזמנת הרצאה זו לארגון שלכם</span>
                  </a>
                </div>
              </div>
            </article>

            {/* Lecture 2: Parenting Guidance & Family Resilience */}
            <article className={styles.lectureCard}>
              <div className={styles.mediaContainer}>
                <div className={styles.mediaBadge}>
                  <FiVideo aria-hidden="true" />
                  <span>הרצאת וידאו</span>
                </div>
                <video 
                  controls 
                  preload="metadata" 
                  className={styles.videoPlayer}
                  poster="/images/lectures/shira_lecture_revava_smile.jpg"
                >
                  <source src="/videos/shira_revava.mp4" type="video/mp4" />
                  הדפדפן שלך אינו תומך בהצגת וידאו.
                </video>
              </div>
              <div className={styles.lectureContent}>
                <div className={styles.cardHeader}>
                  <span className={styles.tag}>הדרכת הורים וחוסן משפחתי</span>
                </div>
                <h3 className={styles.lectureTitle}>להיות מגדלור בעת סערה: הנחיית הורים וחוסן משפחתי</h3>
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
                <div className={styles.cardFooter}>
                  <a 
                    href={SITE_CONFIG.links.whatsapp}
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className={styles.cardActionLink}
                  >
                    <FiMessageCircle aria-hidden="true" />
                    <span>הזמנת הרצאה זו לארגון שלכם</span>
                  </a>
                </div>
              </div>
            </article>

            {/* Lecture 3: Y.N.R Revava */}
            <article className={styles.lectureCard}>
              <div className={styles.mediaContainer}>
                <div className={styles.mediaBadge}>
                  <FiCamera aria-hidden="true" />
                  <span>תיעוד מסדנה</span>
                </div>
                <img 
                  src="/images/lectures/ynr_lecture_classroom.jpg" 
                  alt="הרצאת שירה סהרוני במדרשת רבבה - מכללת י.נ.ר"
                  className={styles.lectureCoverImage}
                  loading="lazy"
                />
              </div>
              <div className={styles.lectureContent}>
                <div className={styles.cardHeader}>
                  <span className={styles.tag}>הומור, זוגיות והעצמה</span>
                </div>
                <h3 className={styles.lectureTitle}>על נישואין בהומור – צחוק והומור לשיפור האווירה המשפחתית והקשר הזוגי</h3>
                <div className={styles.metaInfo}>
                  <div className={styles.metaItem}>
                    <FiMapPin aria-hidden="true" />
                    <span>מדרשת רבבה (מכללת י.נ.ר - לימודי ייעוץ וטיפול)</span>
                  </div>
                  <div className={styles.metaItem}>
                    <FiCalendar aria-hidden="true" />
                    <span>מדרשת רבבה להעצמה אישית ומשפחתית</span>
                  </div>
                </div>
                <p className={styles.description}>
                  הרצאה סוחפת, מעצימה ומלאת הומור שניתנה על ידי שירה סהרוני במדרשת רבבה. ההרצאה עוסקת בכוחם של הצחוק וההומור לפרוק מתחים יומיומיים, לגשר על פערי תקשורת, לחזק את האינטימיות והחברות בין בני הזוג, ולשפר את האווירה הכללית בבית ובמשפחה. (בנוסף ניתנה במדרשה הרצאה מקצועית בנושא התמודדות רגשית עם אתגרי הרווקות המאוחרת).
                </p>
                <div className={styles.cardFooter}>
                  <a 
                    href="https://www.facebook.com/ynrcollege/posts/pfbid02FKpfmoVzzvvw8jDehMsveAJFygoMJwow73NJML6TRzVJkcszK1CFGVfwM2oWR3RPl" 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className={styles.externalLink}
                  >
                    <FiExternalLink aria-hidden="true" />
                    <span>צפייה בפרסום המקורי של מכללת י.נ.ר בפייסבוק</span>
                  </a>
                </div>
              </div>
            </article>

          </div>

          {/* Photo Gallery Section */}
          <div className={styles.gallerySection}>
            <div className={styles.galleryHeading}>
              <h2 className={styles.galleryTitle}>רגעים מתוך ההרצאות והסדנאות</h2>
              <p className={styles.gallerySubtitle}>
                תמונות נבחרות מהרצאות, כנסים וסדנאות בהנחיית שירה סהרוני
              </p>
            </div>
            <div className={styles.galleryGrid}>
              <article className={styles.galleryCard}>
                <div className={styles.galleryImageWrapper}>
                  <img 
                    src="/images/lectures/shira_lecture_ashdod_podium.jpg" 
                    alt="שירה סהרוני בהרצאה במרכז מהו״ת אשדוד"
                    className={styles.galleryImage}
                    loading="lazy"
                  />
                  <div className={styles.galleryOverlay}>
                    <span>נוכחות בימתית על הפודיום</span>
                  </div>
                </div>
                <div className={styles.galleryCaption}>
                  מרכז מהו״ת אשדוד
                </div>
              </article>

              <article className={styles.galleryCard}>
                <div className={styles.galleryImageWrapper}>
                  <img 
                    src="/images/lectures/shira_lecture_ashdod_gesture.jpg" 
                    alt="שירה סהרוני בהדרכה והסבר דינמי בהרצאה"
                    className={styles.galleryImage}
                    loading="lazy"
                  />
                  <div className={styles.galleryOverlay}>
                    <span>הדרכה מעמיקה והבעה דינמית</span>
                  </div>
                </div>
                <div className={styles.galleryCaption}>
                  מרכז מהו״ת אשדוד
                </div>
              </article>

              <article className={styles.galleryCard}>
                <div className={styles.galleryImageWrapper}>
                  <img 
                    src="/images/lectures/shira_lecture_revava_smile.jpg" 
                    alt="שירה סהרוני בקשר חם ומחייך עם הקהל בהרצאה"
                    className={styles.galleryImage}
                    loading="lazy"
                  />
                  <div className={styles.galleryOverlay}>
                    <span>קשר חם ומחייך עם הקהל</span>
                  </div>
                </div>
                <div className={styles.galleryCaption}>
                  הרצאה מקצועית למנחים
                </div>
              </article>

              <article className={styles.galleryCard}>
                <div className={styles.galleryImageWrapper}>
                  <img 
                    src="/images/lectures/shira_lecture_revava_speaking.jpg" 
                    alt="שירה סהרוני בהנחיה מקצועית"
                    className={styles.galleryImage}
                    loading="lazy"
                  />
                  <div className={styles.galleryOverlay}>
                    <span>הנחיה מקצועית ומעצימה</span>
                  </div>
                </div>
                <div className={styles.galleryCaption}>
                  מדרשת רבבה
                </div>
              </article>
            </div>
          </div>

          {/* Bottom CTA Box */}
          <div className={styles.ctaBox}>
            <div className={styles.ctaContent}>
              <h3 className={styles.ctaTitle}>מעוניינים להזמין הרצאה או סדנה לארגון שלכם?</h3>
              <p className={styles.ctaDescription}>
                הרצאות חווייתיות ומעשירות המותאמות במיוחד לצוותי חינוך, ארגונים, חברות, קהילות וקבוצות הורים.
              </p>
              <div className={styles.ctaActions}>
                <a 
                  href={SITE_CONFIG.links.whatsapp}
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className={styles.ctaButtonPrimary}
                >
                  <FiMessageCircle aria-hidden="true" />
                  <span>תיאום הרצאה בוואטסאפ</span>
                </a>
                <a 
                  href={`tel:${SITE_CONFIG.contact.phone}`} 
                  className={styles.ctaButtonSecondary}
                >
                  <FiPhone aria-hidden="true" />
                  <span>{SITE_CONFIG.contact.phone}</span>
                </a>
              </div>
            </div>
          </div>

        </div>
      </section>
    </div>
  );
};

export default LecturesPage;
