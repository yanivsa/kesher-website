import React from 'react';
import { Link } from 'react-router-dom';
import { FiCompass, FiHeart, FiMessageCircle, FiRefreshCw, FiShield, FiUser } from 'react-icons/fi';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from '../shared/SpecialtyServicePage.module.css';

const blogHref = '/blog?category=זוגיות&subcategory=רווקות מאוחרת';

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Service',
      name: 'ייעוץ במצבי רווקות מאוחרת',
      serviceType: 'ייעוץ אישי במצבי רווקות מאוחרת',
      url: `${SITE_CONFIG.url}/services/late-singleness`,
      provider: { '@type': 'LocalBusiness', '@id': `${SITE_CONFIG.url}/#business` },
      description: 'ייעוץ אישי לרווקות ולרווקים המתמודדים עם שחיקה, לחץ מהסביבה, בדידות ודפוסים חוזרים, באשדוד ובאונליין.',
      areaServed: 'ישראל',
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'עמוד הבית', item: SITE_CONFIG.url },
        { '@type': 'ListItem', position: 2, name: 'ייעוץ במצבי רווקות מאוחרת', item: `${SITE_CONFIG.url}/services/late-singleness` },
      ],
    },
  ],
};

const LateSinglenessPage: React.FC = () => (
  <div className={styles.page}>
    <MetaTags
      title="ייעוץ במצבי רווקות מאוחרת"
      description="ייעוץ אישי לרווקות ולרווקים סביב שחיקה, לחץ מהסביבה, בדידות ודפוסים חוזרים — באשדוד ובאונליין."
      image="/images/generated/services/couples-room.jpg"
    />
    <SchemaOrg data={schemaData} />

    <header className={styles.hero}>
      <div className={`container ${styles.heroGrid}`}>
        <div>
          <span className={styles.eyebrow}><FiHeart aria-hidden="true" /> מקום לדבר על התקופה עצמה</span>
          <h1>ייעוץ במצבי רווקות מאוחרת</h1>
          <p className={styles.lead}>
            רווקות שנמשכת מעבר למה שקיוויתם יכולה להביא איתה עייפות, השוואות ושאלות שלא תמיד נעים לענות עליהן. הייעוץ מאפשר להבין מה מכביד עכשיו, בלי להציג את הרווקות כתקלה ובלי לחפש הסבר אחד לכל מה שקרה עד היום.
          </p>
          <div className={styles.heroActions}>
            <Link to={SITE_CONFIG.links.appointment} className={styles.primaryButton}>קביעת פגישת ייעוץ</Link>
            <Link to="/services/finding-relationship" className={styles.secondaryButton}>ליווי מעשי למציאת זוגיות</Link>
          </div>
        </div>
        <aside className={styles.heroPanel} aria-label="נושאים בייעוץ לרווקות מאוחרת">
          <h2>אפשר להביא לפגישה</h2>
          <ul className={styles.checkList}>
            <li>שחיקה, בדידות או אובדן תקווה</li>
            <li>לחץ ושאלות מהמשפחה ומהחברים</li>
            <li>השוואה לאחרים ותחושת החמצה</li>
            <li>דפוסים שחוזרים בקשרים ובהיכרויות</li>
          </ul>
        </aside>
      </div>
    </header>

    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>כשהרווקות תופסת יותר מדי מקום</h2>
          <p>המטרה אינה לשכנע אתכם לחשוב חיובי. בודקים מה שוחק, מה עדיין חשוב לכם ואיך לחיות ולהכיר בלי שכל שבוע יימדד לפי השאלה אם התחיל קשר.</p>
        </div>
        <div className={styles.cardGrid}>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiUser aria-hidden="true" /></span>
            <h3>תחושת ערך וזהות</h3>
            <p>מפרידים בין המצב הזוגי לבין הדרך שבה אתם רואים את עצמכם, במיוחד בתקופות שבהן נדמה שכולם כבר המשיכו הלאה.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiMessageCircle aria-hidden="true" /></span>
            <h3>לחץ מהסביבה</h3>
            <p>מנסחים גבולות ותשובות לשאלות חוזרות, בלי לנתק קשר ובלי להמשיך להסביר את עצמכם בכל ארוחה משפחתית.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiRefreshCw aria-hidden="true" /></span>
            <h3>דפוסים שחוזרים</h3>
            <p>מסתכלים על מי מושך אתכם, מתי אתם נסגרים ואילו קשרים מקבלים שוב ושוב יותר זמן ממה שנכון לכם.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiShield aria-hidden="true" /></span>
            <h3>התמודדות עם דחייה</h3>
            <p>נותנים מקום לאכזבה בלי להפוך כל תשובה שלילית להוכחה שמשהו אצלכם לא בסדר.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiCompass aria-hidden="true" /></span>
            <h3>רצונות מול ציפיות</h3>
            <p>מבררים מה אתם באמת רוצים בקשר, ומה נכנס לרשימה בגלל גיל, לחץ או עצות של אנשים אחרים.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiHeart aria-hidden="true" /></span>
            <h3>חיים מלאים גם עכשיו</h3>
            <p>מחזירים מקום לחברות, למשפחה, לעבודה ולדברים שמחזיקים אתכם, בלי לוותר על הרצון בזוגיות.</p>
          </article>
        </div>
      </div>
    </section>

    <section className={styles.softSection}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>איך נראה הייעוץ?</h2>
          <p>מתחילים במה שקורה בתקופה הנוכחית ובוחרים מוקד אחד שאפשר לעבוד עליו, בלי להבטיח תוצאה שאין לאיש שליטה עליה.</p>
        </div>
        <div className={styles.processGrid}>
          <article className={styles.processStep}><h3>ממפים את העומס</h3><p>מזהים באילו מצבים הרווקות נעשית קשה במיוחד ומה אתם עושים כשזה קורה.</p></article>
          <article className={styles.processStep}><h3>מדייקים צורך</h3><p>בוחרים אם להתמקד בלחץ, בדפוס קשר, בהתמודדות עם דחייה או בחזרה הדרגתית להיכרויות.</p></article>
          <article className={styles.processStep}><h3>בודקים שינוי במציאות</h3><p>מנסים תגובה או גבול חדש, חוזרים עם מה שקרה וממשיכים משם.</p></article>
        </div>
      </div>
    </section>

    <section className={styles.softSection}>
      <div className="container">
        <div className={styles.highlight}>
          <h2>מאמרים על רווקות מאוחרת</h2>
          <p>מאמרים על שחיקה, בדידות, לחץ מהסביבה, דחייה והיכולת לשמור על חיים מלאים לצד הרצון בזוגיות.</p>
          <Link to={blogHref} className={styles.secondaryButton}>למאמרים בנושא</Link>
        </div>
      </div>
    </section>

    <section className={styles.cta}>
      <div className="container">
        <h2>לא צריך להתמודד עם כל השאלות לבד</h2>
        <p>אפשר לקיים פגישות באשדוד או אונליין.</p>
        <a href={SITE_CONFIG.links.whatsapp} className={styles.primaryButton}>שליחת הודעה לשירה</a>
      </div>
    </section>
  </div>
);

export default LateSinglenessPage;
