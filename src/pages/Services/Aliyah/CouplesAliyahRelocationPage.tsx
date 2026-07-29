import React from 'react';
import { Link } from 'react-router-dom';
import { FiCompass, FiHeart, FiRefreshCw, FiMessageCircle, FiHome, FiGlobe } from 'react-icons/fi';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from '../shared/SpecialtyServicePage.module.css';

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Service',
      name: 'ייעוץ זוגי לעולים ולמבצעי רילוקיישן',
      serviceType: 'ליווי זוגי במעברים בינלאומיים',
      url: `${SITE_CONFIG.url}/services/couples-aliyah-relocation`,
      provider: {
        '@type': 'LocalBusiness',
        '@id': `${SITE_CONFIG.url}/#business`,
      },
      description: 'ייעוץ זוגי להתמודדות עם משברי רילוקיישן, עלייה לישראל וחזרה לארץ. טיפול בבדידות, פערי שפה ושינוי סטטוס מקצועי.',
      areaServed: 'ישראל וחו"ל (אונליין)',
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: 'עמוד הבית',
          item: SITE_CONFIG.url,
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: 'זוגיות בעלייה וברילוקיישן',
          item: `${SITE_CONFIG.url}/services/couples-aliyah-relocation`,
        },
      ],
    },
  ],
};

const CouplesAliyahRelocationPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags
        title="ייעוץ זוגי לעולים ולמשפחות ברילוקיישן"
        description="ייעוץ זוגי למשברי רילוקיישן ועלייה: התמודדות עם בדידות, פערי שפה, אובדן סטטוס מקצועי ומרחק מרשת התמיכה. פגישות אונליין מכל מקום בעולם."
        image="/images/generated/site/relocation-hero.jpg"
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.hero}>
        <div className={`container ${styles.heroGrid}`}>
          <div>
            <span className={styles.eyebrow}><FiGlobe aria-hidden="true" /> שומרים על הזוגיות בכל מקום</span>
            <h1>ייעוץ זוגי לעולים ולזוגות ברילוקיישן</h1>
            <p className={styles.lead}>
              מעבר מדינה – בין אם בעלייה לישראל או ברילוקיישן לחו"ל – הוא רעידת אדמה לזוגיות. כשהכל בחוץ חדש ולא מוכר, הלחץ והציפיות מתנקזים ישירות לקשר הזוגי.
            </p>
            <div className={styles.heroActions}>
              <Link to={SITE_CONFIG.links.appointment} className={styles.primaryButton}>קביעת שיחת ייעוץ (אונליין/פרונטלי)</Link>
              <Link to="/contact" className={styles.secondaryButton}>פרטים ליצירת קשר</Link>
            </div>
            <div style={{ marginTop: '1.5rem' }}>
              <Link to="/blog/relocation-couple-conversations-before-moving" className={styles.textLink}>
                קראו עוד: 7 שיחות שחייבים לעשות לפני שאורזים &larr;
              </Link>
            </div>
          </div>
          <aside className={styles.heroPanel} aria-label="אתגרי זוגיות במעברים">
            <h2>נקודות שבירה נפוצות</h2>
            <ul className={styles.checkList}>
              <li>בן הזוג ה"נגרר" מול בן הזוג שקריירתו זינקה</li>
              <li>פערים קיצוניים בקצב ההסתגלות והשפה</li>
              <li>בדידות עמוקה ואובדן רשת תמיכה</li>
              <li>תחושת ניכור וגעגוע אל מול ציפייה לאושר</li>
            </ul>
          </aside>
        </div>
      </header>

      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>כשהחלום פוגש את המציאות</h2>
            <p>
              לרוב מעבר מדינה מלווה בהמון תקוות. אבל כשנוחתים, מתגלה לעיתים מציאות קשוחה של בירוקרטיה, קשיי תעסוקה ושאלות של זהות ושייכות.
            </p>
          </div>
          <div className={styles.twoColumns}>
            <article className={styles.column}>
              <span className={styles.cardIcon}><FiCompass aria-hidden="true" /></span>
              <h3>דינמיקת הקריירה והמעמד</h3>
              <p>באופן שכיח ברילוקיישן, אחד מבני הזוג עובר בעקבות עבודה, ואילו השני נדרש להקריב את המסלול שלו ולעיתים לא יכול לעבוד. חוסר האיזון הזה עלול לייצר:</p>
              <ul className={styles.plainList}>
                <li>תחושת ביטול עצמי ותלות כלכלית</li>
                <li>מרמור מצטבר והאשמות הדדיות</li>
                <li>בדידות של בן הזוג שנשאר בבית מול המעגל החברתי של בן הזוג שעובד</li>
              </ul>
            </article>
            <article className={styles.column}>
              <span className={styles.cardIcon}><FiHeart aria-hidden="true" /></span>
              <h3>המעמסה הבלעדית על הזוגיות</h3>
              <p>בארץ המקור היו חברים, משפחה וקולגות לחלוק איתם תסכולים. בסביבה החדשה – בן/בת הזוג הופכים להיות הכל. הכתובת היחידה.</p>
              <ul className={styles.plainList}>
                <li>עומס רגשי אדיר על הקשר שמוביל לפיצוצים</li>
                <li>תחושת "אני לבד במערכה"</li>
                <li>קשיי תקשורת כשלכל אחד יש דרך התמודדות שונה עם לחץ</li>
              </ul>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.softSection}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>איך מחזירים את היציבות?</h2>
            <p>הייעוץ מספק מרחב ניטרלי ומכיל לעבד את האובדן ואת הקשיים, מבלי להיכנס למגננה.</p>
          </div>
          <div className={styles.cardGrid}>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiMessageCircle aria-hidden="true" /></span>
              <h3>הפסקת מעגל ההאשמות</h3>
              <p>ללמוד לתקשר את הקושי בלי להאשים: "אתה הבאת אותנו לפה" או "את לא מנסה מספיק". הבנת המחירים שכל אחד משלם ומתן לגיטימציה לקושי.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiRefreshCw aria-hidden="true" /></span>
              <h3>איזון מחדש של כוחות</h3>
              <p>חלוקה מחודשת של תחומי האחריות בבית ומציאת משמעות ועצמאות עבור בן הזוג שהקריב את שגרתו לטובת המעבר.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiHome aria-hidden="true" /></span>
              <h3>בניית עוגנים בתוך השגרה</h3>
              <p>יצירת טקסים זוגיים והסכמות משותפות שמייצרות אי של יציבות ותחושת "בית", גם כשנמצאים אלפי קילומטרים מארץ המקור.</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.cta}>
        <div className="container">
          <h2>אתם לא חייבים לעבור את משבר הרילוקיישן לבד</h2>
          <p>הליווי ניתן באונליין (Zoom/Meet) בהתאמה לאזורי זמן שונים, או פרונטלית בקליניקה באשדוד לעולים חדשים.</p>
          <a href={SITE_CONFIG.links.whatsapp} className={styles.primaryButton}>פנייה לשירה לקביעת ייעוץ אונליין/פרונטלי</a>
        </div>
      </section>
    </div>
  );
};

export default CouplesAliyahRelocationPage;
