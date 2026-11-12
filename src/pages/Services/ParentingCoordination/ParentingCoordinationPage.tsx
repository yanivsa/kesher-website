import React from 'react';
import { Link } from 'react-router-dom';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import { pushAnalyticsEvent } from '../../../lib/analytics';
import styles from '../shared/SpecialtyServicePage.module.css';

const path = '/services/parenting-coordination';
const url = SITE_CONFIG.url + path;
const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Service',
      '@id': url + '#service',
      name: 'תיאום הורי',
      serviceType: 'Parenting coordination',
      description: 'מידע ובירור התאמה לתיאום הורי עבור הורים פרודים או גרושים המתמודדים עם קונפליקט מתמשך סביב הילדים.',
      url,
      areaServed: { '@type': 'City', name: 'אשדוד' },
      provider: { '@id': SITE_CONFIG.url + '/#business' },
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'עמוד הבית', item: SITE_CONFIG.url },
        { '@type': 'ListItem', position: 2, name: 'תיאום הורי', item: url },
      ],
    },
  ],
};

const trackInquiry = () => pushAnalyticsEvent('service_inquiry_start', { service_type: 'parenting_coordination', cta_location: 'service_page' });

const ParentingCoordinationPage: React.FC = () => (
  <div className={styles.page} data-analytics-service-type="parenting_coordination">
    <MetaTags
      title="תיאום הורי באשדוד | הורות משותפת לאחר פרידה | שירה סהרוני"
      description="מהו תיאום הורי, למי התהליך יכול להתאים ואיך מתמודדים עם מחלוקות מתמשכות סביב הילדים? מידע ובירור התאמה באשדוד עם שירה סהרוני."
      canonical={url}
      image="/images/generated/services/parenting-room.jpg"
    />
    <SchemaOrg data={schemaData} />

    <header className={styles.hero}>
      <div className={'container ' + styles.heroGrid}>
        <div>
          <span className={styles.eyebrow}>הורות משותפת לאחר פרידה</span>
          <h1>תיאום הורי באשדוד — כשהזוגיות מסתיימת, ההורות ממשיכה</h1>
          <p className={styles.lead}>
            כשכל החלטה בנוגע לילדים הופכת לוויכוח, קשה לנהל שגרה יציבה. תיאום הורי הוא
            תהליך מובנה שמטרתו לסייע להורים פרודים או גרושים להתמודד עם מחלוקות הקשורות
            לילדיהם, להפחית את עוצמת הקונפליקט וליישם הסדרי הורות קיימים. לפני שמתחילים
            חשוב לבדוק את התאמת המשפחה ואת מסגרת התהליך.
          </p>
          <div className={styles.heroActions}>
            <Link to="/contact?service=parenting_coordination" onClick={trackInquiry} className={styles.primaryButton}>בירור ראשוני והתאמה</Link>
            <Link to="/blog/category/parenting-coordination" className={styles.secondaryButton}>למאמרים בנושא</Link>
          </div>
        </div>
        <aside className={styles.heroPanel} aria-label="מטרות התהליך">
          <h2>במה מתמקדים?</h2>
          <ul className={styles.checkList}>
            <li>צרכי הילדים וטובתם במרכז השיח</li>
            <li>הפרדה בין קונפליקט זוגי להחלטות הוריות</li>
            <li>תקשורת עניינית ככל שהמצב מאפשר</li>
            <li>בירור התאמה וגבולות תפקיד מראש</li>
          </ul>
        </aside>
      </div>
    </header>

    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>למי מיועד תיאום הורי?</h2>
          <p>ההליך מתואר בהנחיות המקצועיות כמענה להורים בפרידה או לאחר גירושין שיש ביניהם מחלוקות מתמשכות בענייני הילדים, לעיתים גם כאשר כבר קיימת תוכנית הורות או החלטה שיפוטית.</p>
        </div>
        <div className={styles.cardGrid}>
          <article className={styles.card}>
            <h3>קושי בקבלת החלטות משותפות</h3>
            <p>בחירת מסגרות, ענייני בריאות, פעילויות ושאלות יומיומיות אחרות חוזרות שוב ושוב למחלוקת במקום לקבל מענה מעשי.</p>
          </article>
          <article className={styles.card}>
            <h3>מחלוקות חוזרות על שגרת הילדים</h3>
            <p>מעברים בין בתים, חגים, חופשות ושינויים בתכנון דורשים כל פעם התכתבות ארוכה או עימות חדש.</p>
          </article>
          <article className={styles.card}>
            <h3>שיח שמתנהל דרך הילדים</h3>
            <p>כאשר הודעות, בקשות או ויכוחים מועברים באמצעות הילדים, חשוב לבנות דרך תקשורת בוגרת ומוגדרת ביניהם.</p>
          </article>
        </div>
      </div>
    </section>

    <section className={styles.softSection}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>איך עשוי להיראות התהליך?</h2>
          <p>המסגרת המדויקת נקבעת רק לאחר בירור התאמה, תנאי ההסכמה או ההפניה והסמכויות שהוגדרו.</p>
        </div>
        <div className={styles.processGrid}>
          <article className={styles.processStep}><h3>מגדירים מסגרת</h3><p>מבררים את הרקע, צרכי הילדים, הסדרי ההורות הקיימים, גבולות הסודיות ומטרות המפגשים.</p></article>
          <article className={styles.processStep}><h3>ממפים מחלוקות</h3><p>מזהים סוגיות שחוזרות על עצמן ומבחינים בין מחלוקות הוריות לבין הסכסוך שבין בני הזוג לשעבר.</p></article>
          <article className={styles.processStep}><h3>בונים דרכי פעולה</h3><p>מגבשים מנגנוני תקשורת, תיעוד ותיאום בהתאם לצורכי הילדים ולמסגרת המוסכמת או המחייבת.</p></article>
        </div>
      </div>
    </section>

    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>תיאום הורי, גישור או הדרכת הורים?</h2>
          <p>אלה שירותים קרובים אך לא זהים. גישור מתמקד בניסיון להגיע להסכמות בין צדדים; הדרכת הורים מתמקדת בדפוסי הורות ובכלים להתמודדות עם הילדים; תיאום הורי מתמקד בניהול מחלוקות מתמשכות וביישום ההורות לאחר פרידה, במסגרת סמכויות מוגדרת.</p>
        </div>
        <p><Link to="/services/mediation">מידע על גישור משפחתי</Link> · <Link to="/parenting-guidance-divorce">הדרכת הורים בתקופת פרידה וגירושין</Link></p>
      </div>
    </section>

    <section className={styles.softSection}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>שאלות נפוצות</h2>
        </div>
        <h3>האם תיאום הורי מתאים לכל משפחה?</h3>
        <p>לא. לפני התחלת התהליך יש לברר את מידת ההתאמה. כאשר קיימים חשש לאלימות, איומים, שליטה או סיכון להורה או לילד, נדרשת הערכת בטיחות מקצועית, ולעיתים המענה המתאים הוא אחר.</p>
        <h3>האם חייבת להיות החלטת בית משפט?</h3>
        <p>המסגרת משתנה לפי ההליך והדין החל. תיאום הורי עשוי להיעשות מכוח החלטה שיפוטית או בהסכמה פרטית, אך אין להסיק מכך שלגורם המתאם סמכות להכריע במחלוקת ללא הסמכה מתאימה.</p>
        <h3>האם תיאום הורי הוא טיפול זוגי או ייעוץ משפטי?</h3>
        <p>לא. התהליך אינו טיפול זוגי ואינו תחליף לייעוץ משפטי, להערכה טיפולית או להגנה במצבי סיכון. יש לברר מראש מה מתועד ולמי ניתן לדווח בהתאם למסגרת.</p>
        <h3>אפשר להגיע רק אחד מההורים?</h3>
        <p>אפשר לברר באופן ראשוני מהן האפשרויות, אך תיאום הורי עצמו מתבסס על מסגרת מוסדרת של עבודה עם ההורים. אופן ההשתתפות נקבע לפי ההסכמה או ההפניה ותנאי ההתאמה.</p>
        <h3>איפה ניתן ללמוד עוד?</h3>
        <p>הסבר מקצועי זמין באתר <a href="https://www.afccnet.org/Resource-Center/Family-Resources/Understanding-the-Parenting-Coordination-Process" target="_blank" rel="noopener noreferrer">AFCC</a> ובאתר <a href="https://brookdale.jdc.org.il/publication/parenting_coordination/" target="_blank" rel="noopener noreferrer">מכון ברוקדייל</a>.</p>
        <div className={styles.heroActions}>
          <Link to="/contact?service=parenting_coordination" onClick={trackInquiry} className={styles.primaryButton}>לבירור ראשוני עם שירה</Link>
          <Link to="/blog/category/parenting-coordination" className={styles.secondaryButton}>לכל המאמרים בתיאום הורי</Link>
        </div>
      </div>
    </section>
  </div>
);

export default ParentingCoordinationPage;
