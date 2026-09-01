import React from 'react';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './NowPage.module.css';

const LAST_UPDATED = '2026-09-01';

const schemaData = {
  '@context': 'https://schema.org',
  '@type': 'WebPage',
  name: 'מה אני עושה עכשיו — שירה סהרוני',
  url: `${SITE_CONFIG.url}/now`,
  dateModified: LAST_UPDATED,
  about: {
    '@type': 'Person',
    '@id': `${SITE_CONFIG.url}/#person`,
    name: SITE_CONFIG.author,
    alternateName: 'Shira Saharoni',
    sameAs: [SITE_CONFIG.links.facebook, SITE_CONFIG.links.instagram],
  },
};

const NowPage: React.FC = () => (
  <div className={styles.page}>
    <SchemaOrg data={schemaData} />
    <MetaTags
      title="מה אני עושה עכשיו"
      description="עמוד ה-Now של שירה סהרוני: התחומים והפרויקטים המקצועיים שבהם היא מתמקדת עכשיו באשדוד ובאונליין."
      image="/images/shira-saharoni.webp"
    />

    <header className={styles.header}>
      <div className="container">
        <span className={styles.eyebrow}>עכשיו / Now</span>
        <h1>מה אני עושה עכשיו</h1>
        <p>העמוד הזה הוא תמונת מצב פשוטה של הדברים שבהם אני מתמקדת בתקופה הזו.</p>
        <small>עודכן לאחרונה: 1 בספטמבר 2026</small>
      </div>
    </header>

    <main className={`container ${styles.content}`}>
      <section className={styles.section} lang="he" dir="rtl">
        <h2>בימים אלה</h2>
        <p>
          אני מקבלת זוגות לייעוץ זוגי ולגישור, בפגישות פרונטליות באשדוד ובמפגשי Zoom למי שנוח להם להיפגש מרחוק.
        </p>
        <p>
          חלק מרכזי מהעבודה שלי מוקדש גם להנחיית הורים: להבין מה קורה בבית, לזהות דפוסים שחוזרים על עצמם ולבנות צעדים מעשיים שמתאימים למשפחה המסוימת שמולי.
        </p>
        <p>
          במקביל אני מפתחת סדנאות והרצאות לזוגות ולהורים, וכותבת תכנים מקצועיים על זוגיות, תקשורת, הורות, גישור ושינויים שהמשפחה עוברת לאורך החיים.
        </p>
        <p>
          אני משתדלת לשמור את העשייה ממוקדת: פחות רעש, יותר הקשבה, בהירות וכלים שאפשר לקחת מהשיחה אל החיים עצמם.
        </p>
      </section>

      <section className={styles.section} lang="en" dir="ltr">
        <h2>What I’m focused on now</h2>
        <p>
          I’m currently working with couples through couples counseling and mediation, meeting in person in Ashdod and online via Zoom.
        </p>
        <p>
          A significant part of my work is also focused on parent guidance: understanding what is happening at home, identifying recurring patterns, and building practical steps that fit each family.
        </p>
        <p>
          Alongside client work, I’m developing workshops and talks for couples and parents, and writing professional content about relationships, communication, parenting, mediation, and family transitions.
        </p>
        <p>
          My aim is to keep the work focused and useful: less noise, more listening, clarity, and tools that can be taken from the conversation into everyday life.
        </p>
      </section>

      <aside className={styles.note}>
        <strong>מהו עמוד Now?</strong>
        <p>זהו עמוד אישי שמתעדכן מדי פעם ומספר במה אני מתמקדת עכשיו — לא קורות חיים ולא רשימת חדשות.</p>
      </aside>
    </main>
  </div>
);

export default NowPage;
