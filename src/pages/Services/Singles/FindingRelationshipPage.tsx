import React from 'react';
import { Link } from 'react-router-dom';
import { FiCheckCircle, FiCompass, FiHeart, FiMessageCircle, FiSearch, FiSliders } from 'react-icons/fi';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from '../shared/SpecialtyServicePage.module.css';

const blogHref = '/blog?category=זוגיות&subcategory=מציאת זוגיות';

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Service',
      name: 'ליווי למציאת זוגיות',
      serviceType: 'ליווי אישי בתהליך היכרות ובניית קשר זוגי',
      url: `${SITE_CONFIG.url}/services/finding-relationship`,
      provider: { '@type': 'LocalBusiness', '@id': `${SITE_CONFIG.url}/#business` },
      description: 'ליווי אישי סביב היכרויות, דייטים, בחירת קשר, תקשורת, גבולות והמעבר מהיכרות לזוגיות, באשדוד ובאונליין.',
      areaServed: 'ישראל',
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'עמוד הבית', item: SITE_CONFIG.url },
        { '@type': 'ListItem', position: 2, name: 'ליווי למציאת זוגיות', item: `${SITE_CONFIG.url}/services/finding-relationship` },
      ],
    },
  ],
};

const FindingRelationshipPage: React.FC = () => (
  <div className={styles.page}>
    <MetaTags
      title="ליווי למציאת זוגיות"
      description="ליווי אישי סביב היכרויות, דייטים, בחירת קשר, תקשורת, גבולות והמעבר מהיכרות לזוגיות — באשדוד ובאונליין."
      image="/images/generated/services/couples-room.jpg"
    />
    <SchemaOrg data={schemaData} />

    <header className={styles.hero}>
      <div className={`container ${styles.heroGrid}`}>
        <div>
          <span className={styles.eyebrow}><FiCompass aria-hidden="true" /> ליווי מעשי בתהליך ההיכרות</span>
          <h1>ליווי למציאת זוגיות</h1>
          <p className={styles.lead}>
            כשלא ברור למי לתת הזדמנות, איך לנהל את הקצב או מה לומר כשמתחיל להיות חשוב, אפשר לעצור ולחשוב יחד. הליווי מתמקד בהחלטות ובשיחות שנמצאות בידיים שלכם — לא בשידוך ולא בנוסחה שמבטיחה זוגיות.
          </p>
          <div className={styles.heroActions}>
            <Link to={SITE_CONFIG.links.appointment} className={styles.primaryButton}>קביעת פגישת ייעוץ</Link>
            <Link to="/services/late-singleness" className={styles.secondaryButton}>ייעוץ במצבי רווקות מאוחרת</Link>
          </div>
        </div>
        <aside className={styles.heroPanel} aria-label="נושאים בליווי למציאת זוגיות">
          <h2>במה אפשר להתמקד?</h2>
          <ul className={styles.checkList}>
            <li>בחירת דרך היכרות וקצב שמתאים לכם</li>
            <li>דיוק צרכים וקריטריונים לבחירה</li>
            <li>תקשורת וגבולות בתחילת קשר</li>
            <li>מעבר מדייטים לקשר הדדי וברור</li>
          </ul>
        </aside>
      </div>
    </header>

    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>מה עושים בין הרצון בזוגיות לדייט הבא?</h2>
          <p>לא מחפשים משפט מושלם או רשימת סימנים סופית. בונים דרך מסודרת יותר להכיר, לבחור, לשאול ולבדוק התאמה לאורך זמן.</p>
        </div>
        <div className={styles.cardGrid}>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiSearch aria-hidden="true" /></span>
            <h3>דרך היכרות</h3>
            <p>בודקים איפה אתם מכירים היום, מה שוחק אתכם ואיזה שילוב בין אפליקציות, חברים ופעילויות אפשר באמת לקיים.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiSliders aria-hidden="true" /></span>
            <h3>קריטריונים לבחירה</h3>
            <p>מבחינים בין צורך חשוב, העדפה גמישה וסינון אוטומטי שאולי מונע מכם להכיר אדם מתאים.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiMessageCircle aria-hidden="true" /></span>
            <h3>שיחה בדייט</h3>
            <p>מתרגלים סקרנות, שיתוף ושאלות ישירות בלי להפוך את המפגש לריאיון ובלי להסתיר את מה שחשוב לכם.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiHeart aria-hidden="true" /></span>
            <h3>לתת הזדמנות</h3>
            <p>בודקים מתי נכון להמשיך לעוד פגישה גם בלי ניצוץ מיידי, ומתי חוסר נוחות מצביע על פער שלא כדאי להתעלם ממנו.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiCheckCircle aria-hidden="true" /></span>
            <h3>הדדיות וזמינות</h3>
            <p>שמים לב לא רק למה שנאמר, אלא גם ליוזמה, לעקביות וליכולת של שני הצדדים לפנות מקום לקשר.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiCompass aria-hidden="true" /></span>
            <h3>מהיכרות לקשר</h3>
            <p>מדברים על קצב, בלעדיות, ציפיות וחששות לפני שחוסר הבהירות הופך לניחושים ולמתח.</p>
          </article>
        </div>
      </div>
    </section>

    <section className={styles.softSection}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>איך נראה הליווי?</h2>
          <p>מגיעים עם מצב ממשי מההיכרויות ובוחרים שינוי קטן שאפשר לבדוק עד הפגישה הבאה.</p>
        </div>
        <div className={styles.processGrid}>
          <article className={styles.processStep}><h3>מגדירים מטרה</h3><p>מחליטים אם לעבוד על יציאה להיכרויות, בחירה, תקשורת או קשר חדש שכבר התחיל.</p></article>
          <article className={styles.processStep}><h3>מתכוננים למצב אמיתי</h3><p>מנסחים שאלה, גבול או דרך פעולה שמתאימים לאדם ולמצב, ולא תסריט קבוע מראש.</p></article>
          <article className={styles.processStep}><h3>לומדים ממה שקרה</h3><p>בודקים את התגובה שלכם ושל הצד השני ומדייקים את הצעד הבא.</p></article>
        </div>
      </div>
    </section>

    <section className={styles.softSection}>
      <div className="container">
        <div className={styles.highlight}>
          <h2>מאמרים על מציאת זוגיות</h2>
          <p>מאמרים על אפליקציות, דייטים, בחירה, תקשורת, גבולות והתקדמות הדרגתית מהיכרות לקשר.</p>
          <Link to={blogHref} className={styles.secondaryButton}>למאמרים בנושא</Link>
        </div>
      </div>
    </section>

    <section className={styles.cta}>
      <div className="container">
        <h2>אפשר לבנות דרך שמתאימה לכם</h2>
        <p>הפגישות מתקיימות באשדוד או אונליין.</p>
        <a href={SITE_CONFIG.links.whatsapp} className={styles.primaryButton}>שליחת הודעה לשירה</a>
      </div>
    </section>
  </div>
);

export default FindingRelationshipPage;
