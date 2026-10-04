import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import MetaTags from '../../components/SEO/MetaTags';
import { SITE_CONFIG } from '../../constants/siteConfig';
import { pushAnalyticsEvent } from '../../lib/analytics';
import styles from './ChatGPTToolsPage.module.css';

const UTM = 'utm_source=chatgpt&utm_medium=plugin&utm_campaign=kesher_plugin';

const ChatGPTToolsPage: React.FC = () => {
  useEffect(() => {
    pushAnalyticsEvent('plugin_landing_view', {
      service_type: 'chatgpt_plugin',
      plugin_version: 'v2',
    });
  }, []);

  const trackResource = (domain: string, location: string) => {
    pushAnalyticsEvent('plugin_resource_click', {
      service_type: 'chatgpt_plugin',
      resource_domain: domain,
      cta_location: location,
    });
  };

  return (
    <main className={styles.page} data-analytics-service-type="chatgpt_plugin">
      <MetaTags
        canonical={`${SITE_CONFIG.url}/tools/chatgpt`}
        title="Kesher ב-ChatGPT | זוגיות והדרכת הורים בעברית"
        description="כלי Kesher ב-ChatGPT לזוגיות, הדרכת הורים ואתגרי קשב ותפקודים ניהוליים — עם פרטיות, גבולות מקצועיים וכלים מעשיים בעברית."
      />

      <section className={styles.hero}>
        <div className="container">
          <p className={styles.eyebrow}>Kesher × ChatGPT</p>
          <h1>כלים מעשיים בעברית לזוגיות, הורות וקשב</h1>
          <p className={styles.lead}>
            Kesher נבנה כדי לתת בתוך ChatGPT מענה מובנה וקצר למצבים יומיומיים:
            להבין דפוס תקשורת זוגי, לתכנן שיחה קשה, להגיב לאתגר הורי,
            או לבנות תמיכה סביב קשב ותפקודים ניהוליים.
          </p>
        </div>
      </section>

      <section className={styles.gridSection} aria-label="תחומי הכלים">
        <div className={`container ${styles.grid}`}>
          <article className={styles.card}>
            <span className={styles.number}>01</span>
            <h2>זוגיות</h2>
            <p>מיפוי מעגלים חוזרים בקונפליקט ותכנון שיחה רגועה יותר, בלי לאבחן או לתייג אף אחד מבני הזוג.</p>
            <Link
              to={`/services/couples?${UTM}&utm_content=couples`}
              onClick={() => trackResource('couples', 'couples_card')}
            >
              מידע נוסף על ליווי זוגי
            </Link>
          </article>

          <article className={styles.card}>
            <span className={styles.number}>02</span>
            <h2>הדרכת הורים</h2>
            <p>גבולות, התפרצויות, מסכים, אחים, שינה, בקרים, מעברים, שיתוף פעולה וקשר עם מתבגרים.</p>
            <Link
              to={`/services/parenting?${UTM}&utm_content=parenting`}
              onClick={() => trackResource('parenting', 'parenting_card')}
            >
              מידע נוסף על הדרכת הורים
            </Link>
          </article>

          <article className={styles.card}>
            <span className={styles.number}>03</span>
            <h2>קשב ותפקודים ניהוליים</h2>
            <p>התארגנות, התחלת משימות, זיכרון עבודה, מעברים, תסכול ומסכים — גם כשיש ADHD וגם כשפשוט יש קושי תפקודי דומה.</p>
            <Link
              to={`/parenting-adhd-ashdod?${UTM}&utm_content=parenting_adhd`}
              onClick={() => trackResource('parenting_adhd', 'adhd_card')}
            >
              מידע נוסף על הורות ו-ADHD
            </Link>
          </article>
        </div>
      </section>

      <section className={styles.boundaries}>
        <div className="container">
          <div className={styles.split}>
            <div>
              <h2>מה הכלים כן עושים</h2>
              <ul>
                <li>מתרגמים מצב מורכב לצעדים קטנים וישימים.</li>
                <li>מציעים ניסוח, מסגרת פעולה או מבנה לשיחה.</li>
                <li>יכולים להפנות, לפי בקשה מפורשת, לתוכן רלוונטי של Kesher.</li>
                <li>משתמשים בשדות כלליים ומובנים במקום להעביר את הסיפור האישי המלא לשרת.</li>
              </ul>
            </div>
            <div>
              <h2>מה הם לא עושים</h2>
              <ul>
                <li>לא מאבחנים ADHD, הפרעה נפשית או מצב רפואי.</li>
                <li>לא ממליצים על תרופות, מינונים או שינוי טיפול.</li>
                <li>לא מספקים ייעוץ משפטי ולא מחליפים מענה במצב אלימות, סכנה או פגיעה עצמית.</li>
                <li>לא אוספים שמות ילדים, בית ספר, טלפון, אימייל או תמלילי שיחות.</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.how}>
        <div className="container">
          <h2>איך זה עובד ב-ChatGPT?</h2>
          <ol>
            <li>שואלים שאלה טבעית בעברית.</li>
            <li>כאשר Kesher מתאים לבקשה וה-Plugin מחובר, ChatGPT יכול לבחור בכלי הממוקד ביותר.</li>
            <li>הכלי מחזיר תשובה מובנית בתוך השיחה. אין חובה לעבור לאתר כדי לקבל ערך.</li>
          </ol>
          <p className={styles.note}>
            זמינות ה-Plugin תלויה בפרסום ובחיבור שלו ב-ChatGPT. לא ניתן להבטיח ש-ChatGPT יבחר בו בכל שאלה.
          </p>
        </div>
      </section>

      <section className={styles.cta}>
        <div className="container">
          <h2>רוצים להכיר את שירה ואת הגישה שמאחורי הכלים?</h2>
          <div className={styles.actions}>
            <Link
              className={styles.primary}
              to={`/about?${UTM}&utm_content=about`}
              onClick={() => trackResource('about', 'closing_about')}
            >
              על שירה סהרוני
            </Link>
            <Link
              className={styles.secondary}
              to={`/blog?${UTM}&utm_content=blog`}
              onClick={() => trackResource('blog', 'closing_blog')}
            >
              למאמרים
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
};

export default ChatGPTToolsPage;
