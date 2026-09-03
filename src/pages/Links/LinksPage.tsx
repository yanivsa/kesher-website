import React from 'react';
import MetaTags from '../../components/SEO/MetaTags';
import styles from './LinksPage.module.css';

const resources = [
  {
    name: 'האגודה הישראלית לטיפול זוגי ומשפחתי',
    url: 'https://mishpaha.org.il/',
    note: 'מידע לציבור על טיפול זוגי ומשפחתי, בחירת מטפל ושירותים מקצועיים בתחום.',
  },
  {
    name: 'הרשות השופטת — יישוב סכסוך במשפחה',
    url: 'https://www.gov.il/he/service/asking_for_family_dispute_settlements',
    note: 'מידע ממשלתי רשמי על הליך יישוב סכסוך במשפחה ופגישות מהו״ת.',
  },
  {
    name: 'מכון אדלר',
    url: 'https://machon-adler.co.il/',
    note: 'מידע, הדרכות ותכנים בתחומי הורות, יחסים ומשפחה.',
  },
  {
    name: 'המועצה לשלום הילד',
    url: 'https://www.children.org.il/',
    note: 'מידע ופעילות בנושאי זכויות, רווחה והגנה על ילדים ובני נוער בישראל.',
  },
];

const LinksPage: React.FC = () => (
  <div className={styles.page}>
    <MetaTags
      title="קישורים ומקורות מקצועיים"
      description="קישורים לארגונים ולמקורות מידע שימושיים בתחומי זוגיות, משפחה, הורות, גישור וזכויות ילדים בישראל."
    />

    <header className={styles.header}>
      <div className="container">
        <span className={styles.eyebrow}>מקורות שימושיים</span>
        <h1>קישורים ומקורות מקצועיים</h1>
        <p>ריכזתי כאן מקורות חיצוניים שיכולים לעזור להעמיק, לבדוק מידע ולהכיר שירותים מקצועיים וציבוריים נוספים.</p>
      </div>
    </header>

    <main className={`container ${styles.content}`}>
      <section aria-labelledby="resources-heading">
        <h2 id="resources-heading">ארגונים ומקורות מידע</h2>
        <div className={styles.grid}>
          {resources.map((resource) => (
            <article className={styles.card} key={resource.url}>
              <h3>
                <a href={resource.url} target="_blank" rel="noopener noreferrer">
                  {resource.name}
                </a>
              </h3>
              <p>{resource.note}</p>
            </article>
          ))}
        </div>
      </section>

      <aside className={styles.disclaimer}>
        <strong>הבהרה</strong>
        <p>
          הקישורים ניתנים כמשאבי מידע בלבד. הופעת גוף או אתר בעמוד אינה מעידה על שיתוף פעולה, חברות, הסמכה או המלצה אישית, והמידע באתרים החיצוניים הוא באחריות מפעיליהם.
        </p>
      </aside>

      <p className={styles.updated}>עודכן לאחרונה: 1 בספטמבר 2026</p>
    </main>
  </div>
);

export default LinksPage;
