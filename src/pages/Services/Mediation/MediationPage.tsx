import React from 'react';
import { Link } from 'react-router-dom';
import { FiBriefcase, FiHome, FiMessageCircle, FiUsers } from 'react-icons/fi';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import TherapistBio from '../../../components/TherapistBio/TherapistBio';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from '../shared/SpecialtyServicePage.module.css';

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Service',
      name: 'גישור',
      alternateName: 'גישור משפחתי וגישור גירושין',
      serviceType: 'גישור משפחתי, זוגי וגישור גירושין',
      url: `${SITE_CONFIG.url}/services/mediation`,
      provider: {
        '@type': 'LocalBusiness',
        '@id': `${SITE_CONFIG.url}/#business`,
      },
      description: 'גישור באשדוד ובאונליין לבני זוג, משפחות והורים, כולל גישור גירושין והגעה להסכמות בנושאי הורות, אחריות, כסף והתנהלות משותפת.',
      image: `${SITE_CONFIG.url}/images/generated/services/mediation-room.jpg`,
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
          name: 'גישור',
          item: `${SITE_CONFIG.url}/services/mediation`,
        },
      ],
    },
  ],
};

const MediationPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags
        canonical={`${SITE_CONFIG.url}/services/mediation`}
        title="גישור גירושין ומשפחתי באשדוד | מגשרת מוסמכת"
        description="גישור גירושין וגישור משפחתי באשדוד ובאונליין: שיחה מסודרת עם מגשרת ניטרלית לבניית הסכמות מעשיות סביב הורות, כסף, אחריות והמשך הדרך."
        image="/images/generated/services/mediation-room.jpg"
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.hero}>
        <div className={`container ${styles.heroGrid}`}>
          <div>
            <span className={styles.eyebrow}><FiMessageCircle aria-hidden="true" /> גישור בגובה העיניים</span>
            <h1>גישור משפחתי וגירושין באשדוד ובאונליין</h1>
            <p className={styles.lead}>
              גישור משפחתי וגישור גירושין הם תהליכים שבהם צדדים שמתקשים להגיע להסכמה מנהלים שיחה מסודרת בנוכחות מגשרת ניטרלית. המגשרת מסייעת למפות את הנושאים, לשמוע את הצרכים של כל צד ולבנות הסכמות מעשיות — בלי להכריע במקומם.
            </p>
            <div className={styles.heroActions}>
              <Link to={SITE_CONFIG.links.appointment} className={styles.primaryButton}>קביעת פגישת ייעוץ</Link>
              <Link to="/about" className={styles.secondaryButton}>אודות שירה</Link>
            </div>
          </div>
          <aside className={styles.heroPanel} aria-label="עקרונות הגישור">
            <h2>מה מקבלים בתהליך?</h2>
            <ul className={styles.checkList}>
              <li>מרחב מכבד ודיסקרטי לכל הצדדים</li>
              <li>מיפוי ברור של הנושאים והצרכים</li>
              <li>שיחה ממוקדת בלי להיתקע בהאשמות</li>
              <li>הסכמות מציאותיות שאפשר ליישם</li>
            </ul>
          </aside>
        </div>
      </header>

      <section className={styles.softSection}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>מה זה גישור גירושין?</h2>
            <p>
              גישור גירושין הוא תהליך שבו בני זוג שנפרדים מנסים להגיע בהסכמה להחלטות שיאפשרו להם להמשיך הלאה בצורה ברורה ומעשית. הנושאים יכולים לכלול הורות משותפת, חלוקת אחריות, התנהלות כלכלית, רכוש והדרך שבה מתקשרים מול הילדים וביניהם.
            </p>
          </div>
          <div className={styles.cardGrid}>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiUsers aria-hidden="true" /></span>
              <h3>על אילו נושאים אפשר להגיע להסכמות?</h3>
              <p>ממפים את הנושאים שדורשים החלטה ובונים הסכמות שמתאימות למשפחה: הורות, שגרה וזמני שהות, אחריות, כסף ורכוש, וכן דרך תקשורת שתאפשר ליישם את ההסכמות ביום־יום.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiMessageCircle aria-hidden="true" /></span>
              <h3>מה תפקיד המגשרת?</h3>
              <p>המגשרת מנהלת את השיחה באופן ניטרלי, עוזרת להפריד בין עמדות לצרכים ושומרת על תהליך מסודר. ההחלטות עצמן נשארות בידי בני הזוג, וההשתתפות וההסכמות מתקבלות מרצון.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiHome aria-hidden="true" /></span>
              <h3>מה קורה כשמגיעים להסכם?</h3>
              <p>
                אם ההסכמות מתגבשות להסכם גירושין, יש להביא אותו לאישור ערכאה שיפוטית מוסמכת כדי שיקבל תוקף של פסק דין. המידע כאן כללי ואינו מחליף ייעוץ משפטי. למידע רשמי ראו{' '}
                <a href="https://www.gov.il/he/service/couple-family-agreement" target="_blank" rel="noopener noreferrer">
                  אישור הסכם גירושין באתר gov.il
                </a>.
              </p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>אפשרויות גישור</h2>
            <p>התהליך מותאם לסוג הקשר, לנושאים שעל הפרק ולקצב שבו ניתן להתקדם.</p>
          </div>
          <div className={styles.cardGrid}>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiMessageCircle aria-hidden="true" /></span>
              <h3>גישור בין בני זוג</h3>
              <p>שיח סביב החלטות משותפות, תקשורת, חלוקת אחריות, כסף, משפחות מוצא ונושאים שחוזרים שוב ושוב ללא פתרון.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiUsers aria-hidden="true" /></span>
              <h3>גישור בתוך המשפחה</h3>
              <p>יצירת שיחה מסודרת בין בני משפחה כשהיחסים חשובים, אך המתח מקשה להקשיב, לדבר ולהגיע להבנות.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiHome aria-hidden="true" /></span>
              <h3>גישור בין הורים</h3>
              <p>בניית שיתוף פעולה סביב גבולות, שגרה, מסגרות חינוכיות וקבלת החלטות הנוגעות לילדים.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiHome aria-hidden="true" /></span>
              <h3>גישור בין שכנים ובקהילה</h3>
              <p>התמודדות עם חיכוכים מתמשכים, שימוש במרחב משותף, רעש, ועד הבית ונושאים קהילתיים.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiBriefcase aria-hidden="true" /></span>
              <h3>גישור במקום העבודה</h3>
              <p>שיפור התקשורת והסדרת ציפיות, אחריות ותהליכי עבודה בין עובדים, מנהלים או צוותים.</p>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}><FiBriefcase aria-hidden="true" /></span>
              <h3>גישור בין שותפים</h3>
              <p>בירור אינטרסים ובניית הסכמות סביב חלוקת תפקידים, קבלת החלטות והמשך עבודה משותפת.</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.softSection}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>איך נראה תהליך הגישור?</h2>
            <p>המטרה אינה לקבוע מי צודק, אלא להבין מה חשוב לכל צד ולבנות דרך ששני הצדדים יכולים לעמוד בה.</p>
          </div>
          <div className={styles.processGrid}>
            <article className={styles.processStep}>
              <h3>מגדירים את הנושאים</h3>
              <p>ממפים מה דורש החלטה, מה יוצר מתח ומה חשוב לכל אחד לשמור לאורך הדרך.</p>
            </article>
            <article className={styles.processStep}>
              <h3>מקשיבים ומבררים</h3>
              <p>כל צד מקבל מקום להציג את נקודת המבט שלו, בעוד השיחה נשארת מסודרת וממוקדת.</p>
            </article>
            <article className={styles.processStep}>
              <h3>בונים הסכמות</h3>
              <p>מפתחים אפשרויות, בוחנים מה ישים ומנסחים הסכמות ברורות שניתן ליישם בחיי היום־יום.</p>
            </article>
          </div>
          <p className={styles.note}>
            ההשתתפות בגישור וההסכמות מתקבלות מרצון. שירה מנהלת את השיחה באופן ניטרלי; ההחלטות נשארות בידי המשתתפים.
          </p>
        </div>
      </section>

      <TherapistBio />

      <section className={styles.cta}>
        <div className="container">
          <h2>אפשר להתחיל משיחה קצרה</h2>
          <p>נבדוק יחד אם גישור הוא המסגרת המתאימה לנושא שמעסיק אתכם.</p>
          <a href={SITE_CONFIG.links.whatsapp} className={styles.primaryButton}>שליחת הודעה לשירה</a>
        </div>
      </section>
    </div>
  );
};

export default MediationPage;
