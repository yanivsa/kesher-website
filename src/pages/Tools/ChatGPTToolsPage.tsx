import React from 'react';
import MetaTags from '../../components/SEO/MetaTags';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './ChatGPTToolsPage.module.css';

const ChatGPTToolsPage: React.FC = () => {
  return (
    <main className={styles.page}>
      <MetaTags
        canonical={`${SITE_CONFIG.url}/tools/chatgpt`}
        title="Kesher ב-ChatGPT | זוגיות והדרכת הורים בעברית"
        description="כלי Kesher ב-ChatGPT לזוגיות, הדרכת הורים וקשיי קשב ותפקודים ניהוליים — עם גבולות פרטיות ובטיחות ברורים."
      />
      <section className={styles.hero}>
        <div className="container">
          <p className={styles.eyebrow}>Kesher ב-ChatGPT</p>
          <h1>כלים מעשיים בעברית לזוגיות ולהדרכת הורים</h1>
          <p className={styles.lead}>
            Kesher מספק ב-ChatGPT כלים מובנים להבנת קונפליקטים זוגיים, לתכנון שיחות קשות,
            להתמודדות הורית יומיומית ולתמיכה סביב קשב ותפקודים ניהוליים.
          </p>
        </div>
      </section>

      <section className={styles.section}>
        <div className="container">
          <div className={styles.grid}>
            <article className={styles.card}>
              <h2>זוגיות</h2>
              <p>הבנת דפוסי ריב חוזרים, הסלמה, ביקורת והתגוננות, ותכנון שיחה רגועה יותר.</p>
            </article>
            <article className={styles.card}>
              <h2>הדרכת הורים</h2>
              <p>גבולות, התפרצויות, אחים, מסכים, שינה, שגרות, מעברים, שיתוף פעולה ומתבגרים.</p>
            </article>
            <article className={styles.card}>
              <h2>קשב ותפקודים ניהוליים</h2>
              <p>התארגנות, התחלת משימות, מעברים, זיכרון עבודה, תסכול ואימפולסיביות — בלי אבחון רפואי.</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.section}>
        <div className="container">
          <h2>מה הכלים לא עושים</h2>
          <ul className={styles.list}>
            <li>לא מאבחנים ADHD או מצב רפואי או נפשי.</li>
            <li>לא נותנים המלצות על תרופות או מינונים.</li>
            <li>לא מחליפים מענה מקצועי במצבי סכנה, אלימות או פגיעה עצמית.</li>
            <li>לא אוספים שמות ילדים, בית ספר, טלפון, אימייל או תמלילי שיחה מלאים.</li>
          </ul>
        </div>
      </section>

      <section className={styles.section}>
        <div className="container">
          <h2>פרטיות</h2>
          <p>
            כלי Kesher משתמשים בשדות כלליים ומובנים בלבד. מידע נוסף מופיע ב
            <a href="/privacy">מדיניות הפרטיות</a>.
          </p>
        </div>
      </section>
    </main>
  );
};

export default ChatGPTToolsPage;
