import React from 'react';
import { Link } from 'react-router-dom';
import { FiCompass, FiHeart, FiHome, FiMessageCircle, FiRefreshCw, FiUsers } from 'react-icons/fi';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from '../shared/SpecialtyServicePage.module.css';

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Service',
      name: 'ייעוץ זוגי והנחיית הורים למשפחות עולים ותושבים חוזרים',
      serviceType: 'ליווי משפחתי בתקופת עלייה או חזרה לישראל',
      url: `${SITE_CONFIG.url}/services/aliyah-families`,
      provider: {
        '@type': 'LocalBusiness',
        '@id': `${SITE_CONFIG.url}/#business`,
      },
      description: 'ייעוץ זוגי והנחיית הורים למשפחות עולים לישראל ולתושבים חוזרים, באשדוד ובאונליין.',
      areaServed: 'ישראל',
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
          name: 'משפחות עולים ותושבים חוזרים',
          item: `${SITE_CONFIG.url}/services/aliyah-families`,
        },
      ],
    },
  ],
};

const AliyahFamiliesPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags
        title="ייעוץ למשפחות עולים ותושבים חוזרים"
        description="ייעוץ זוגי והנחיית הורים למשפחות עולים ותושבים חוזרים: הסתגלות, מסגרות חינוכיות, זוגיות, הורות ושייכות."
        image="/images/generated/site/home-hero.jpg"
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.hero}>
        <div className={`container ${styles.heroGrid}`}>
          <div>
            <span className={styles.eyebrow}><FiCompass aria-hidden="true" /> ליווי בתקופת שינוי</span>
            <h1>ייעוץ זוגי והנחיית הורים למשפחות עולים ותושבים חוזרים</h1>
            <p className={styles.lead}>
              עלייה או חזרה לישראל היא שינוי של מדינה, שפה, מסגרת ולעיתים גם זהות משפחתית. גם כשהמעבר רצוי, הוא יכול להעמיס על הזוגיות, ההורות והילדים.
            </p>
            <div className={styles.heroActions}>
              <Link to={SITE_CONFIG.links.appointment} className={styles.primaryButton}>קביעת פגישת ייעוץ</Link>
              <Link to="/services/couples-aliyah-relocation" className={styles.secondaryButton}>ייעוץ זוגי סביב עלייה ורילוקיישן</Link>
            </div>
          </div>
          <aside className={styles.heroPanel} aria-label="נושאים בליווי משפחות עולים">
            <h2>המעבר משפיע על כולם</h2>
            <ul className={styles.checkList}>
              <li>פערים בקצב ההסתגלות בין בני המשפחה</li>
              <li>כניסה למסגרות חינוכיות חדשות</li>
              <li>שינוי בתפקידים וברשת התמיכה</li>
              <li>בניית תחושת בית ושייכות בישראל</li>
            </ul>
          </aside>
        </div>
      </header>

      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>מענה זוגי והורי תחת קורת גג אחת</h2>
            <p>
              הליווי נותן מקום לפערים בין בני המשפחה ובונה כלים מעשיים להתארגנות, תקשורת ושייכות בתקופת המעבר.
            </p>
          </div>
          <div className={styles.twoColumns}>
            <article className={styles.column}>
              <span className={styles.cardIcon}><FiHeart aria-hidden="true" /></span>
              <h3>ייעוץ זוגי</h3>
              <p>המעבר יכול להעלות שאלות זוגיות שלא היו קודם, או להעצים דפוסים קיימים.</p>
              <ul className={styles.plainList}>
                <li>פער בקצב ההסתגלות בין בני הזוג</li>
                <li>עומס כלכלי, תעסוקתי וחברתי</li>
                <li>אובדן רשת תמיכה ותחושת בדידות</li>
                <li>חלוקת תפקידים חדשה בבית</li>
                <li>געגוע, ספק ושאלות של שייכות</li>
              </ul>
            </article>
            <article className={styles.column}>
              <span className={styles.cardIcon}><FiUsers aria-hidden="true" /></span>
              <h3>הנחיית הורים</h3>
              <p>הילדים פוגשים מסגרת, שפה וקודים חברתיים חדשים, בזמן שגם ההורים עדיין מסתגלים.</p>
              <ul className={styles.plainList}>
                <li>כניסה למסגרת חינוכית חדשה</li>
                <li>פערי שפה ותרבות</li>
                <li>תגובות רגשיות של ילדים למעבר</li>
                <li>בניית שגרה ותחושת בית</li>
                <li>שמירה על סמכות הורית בתקופת אי־ודאות</li>
              </ul>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.softSection}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>אתגרים נפוצים בתקופת המעבר</h2>
            <p>כל בן משפחה עשוי לחוות את המעבר אחרת. המטרה היא לא לדרוש מכולם להסתגל באותו קצב, אלא ליצור דרך משפחתית משותפת.</p>
          </div>
          <div className={styles.cardGrid}>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiRefreshCw aria-hidden="true" /></span>
              <h3>שינוי תפקידים</h3>
              <p>מי שעבד, ניהל או היה מוקף במשפחה ובחברים עשוי למצוא את עצמו בתפקיד אחר לחלוטין אחרי המעבר.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiMessageCircle aria-hidden="true" /></span>
              <h3>פערי שפה ותקשורת</h3>
              <p>פערי שפה אינם רק עניין טכני; הם משפיעים על עצמאות, ביטחון, קשר עם המסגרת והיכולת לבקש עזרה.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiHome aria-hidden="true" /></span>
              <h3>בניית תחושת בית</h3>
              <p>מחברים בין המוכר שהמשפחה הביאה איתה לבין החיים החדשים, כדי ליצור רצף, שגרה ותחושת שייכות.</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.softSection}>
        <div className="container">
          <div className={styles.highlight}>
            <h2>לא צריך לחכות עד שהעומס יהפוך למשבר</h2>
            <p>
              אפשר להשתמש בתקופת המעבר כדי לנסח מחדש ציפיות, לחלק אחריות, להבין מה כל אחד מבני המשפחה צריך ולבנות הרגלים שתומכים בבית החדש.
            </p>
          </div>
          <div className={styles.processGrid}>
            <article className={styles.processStep}>
              <h3>מזהים את מוקדי העומס</h3>
              <p>מבינים מה השתנה, מי מתקשה ובאילו מצבים הבית מאבד יציבות או שיתוף פעולה.</p>
            </article>
            <article className={styles.processStep}>
              <h3>מגדירים מטרות קרובות</h3>
              <p>בוחרים נושא מעשי אחד בכל פעם: שגרה, תקשורת זוגית, מסגרת חינוכית או חלוקת אחריות.</p>
            </article>
            <article className={styles.processStep}>
              <h3>בונים שגרה חדשה</h3>
              <p>מפתחים כלים שמתאימים לחיים בישראל ומחזקים בהדרגה ביטחון, שייכות ועצמאות.</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.cta}>
        <div className="container">
          <h2>המעבר הוא משפחתי — וגם הליווי יכול להיות כזה</h2>
          <p>אפשר לקיים פגישות באשדוד או אונליין מכל מקום בארץ.</p>
          <a href={SITE_CONFIG.links.whatsapp} className={styles.primaryButton}>שליחת הודעה לשירה</a>
        </div>
      </section>
    </div>
  );
};

export default AliyahFamiliesPage;
