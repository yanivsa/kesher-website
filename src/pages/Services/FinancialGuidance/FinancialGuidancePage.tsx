import React from 'react';
import { Link } from 'react-router-dom';
import { FiBookOpen, FiHeart, FiHome, FiUsers } from 'react-icons/fi';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from '../shared/SpecialtyServicePage.module.css';

const path = '/services/family-financial-guidance';
const url = SITE_CONFIG.url + path;
const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    { '@type': 'Service', '@id': url + '#service', name: 'ליווי כלכלי לזוגות ומשפחות', serviceType: 'חינוך פיננסי וליווי להתנהלות כלכלת המשפחה',
      url, provider: { '@id': SITE_CONFIG.url + '/#business', '@type': 'LocalBusiness' }, areaServed: [
      { '@type': 'City', name: 'אשדוד' }, { '@type': 'Country', name: 'ישראל' }],
      description: 'ליווי המשלב חינוך פיננסי, שיח זוגי, תכנון תקציב והרגלי התנהלות כלכלית בבית. אינו ייעוץ השקעות, פנסיה או מס.',
      image: SITE_CONFIG.url + '/images/financial-guidance/family-financial-guidance.svg' },
    { '@type': 'BreadcrumbList', '@id': url + '#breadcrumb', itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'עמוד הבית', item: SITE_CONFIG.url },
      { '@type': 'ListItem', position: 2, name: 'ליווי כלכלי לזוגות ומשפחות', item: url }] },
  ],
};
const FinancialGuidancePage: React.FC = () => (
  <div className={styles.page}>
    <MetaTags title="ליווי כלכלי לזוגות ומשפחות" description="ליווי כלכלי לזוגות ולמשפחות באשדוד ובאונליין: סדר בהוצאות, תקציב משפחתי, תקשורת זוגית סביב כסף וחינוך פיננסי בגישה מעשית." canonical={url} image="/images/generated/site/home-hero.jpg" />
    <SchemaOrg data={schemaData} />
    <header className={styles.hero}>
      <div className={`container ${styles.heroGrid}`}>
        <div>
          <h1>ליווי כלכלי לזוגות ומשפחות — לעשות סדר בכסף ובשיח בבית</h1>
          <p className={styles.lead}>התנהלות כלכלית אינה רק רשימת מספרים. היא גם סדרי עדיפויות, שיחות שקשה לפתוח, הרגלים שהצטברו והחלטות שמקבלים יחד. שירה סהרוני משלבת חינוך פיננסי עם ניסיון בליווי זוגי ומשפחתי כדי לסייע לכם להבין את התמונה ולבחור צעדים מעשיים שמתאימים לבית שלכם.</p>
          <p>אפשר לבחון יחד את התקציב המשפחתי, ללמוד לנהל שיחות על הוצאות וחיסכון ולבנות הסכמות שמתאימות לאנשים שחיים בבית. אין צורך לחשוף נתוני חשבון או חובות בטופס הפנייה הראשוני.</p>
          <div className={styles.heroActions}>
            <Link className={styles.primaryButton} to={SITE_CONFIG.links.appointment}>בירור התאמה וקביעת פגישה</Link>
            <Link className={styles.secondaryButton} to="/blog/category/family-finances">לקריאת מאמרים וכלים</Link>
          </div>
        </div>
        <aside className={styles.heroPanel}>
          <div className={styles.heroMedia}><img src="/images/financial-guidance/family-financial-guidance.svg" width="1200" height="675" alt="איור מחברת תקציב, לוח תכנון ושני ספלי קפה כסמל לשיחה כלכלית משותפת" fetchPriority="high" /></div>
          <h2>באילו מצבים הליווי יכול להתאים?</h2>
          <ul className={styles.checkList}><li>ויכוחים חוזרים על הוצאות וקניות</li><li>תקציב ביתי שאינו מתוכנן מראש</li><li>פערים בין בני זוג בגישה לחיסכון ולצריכה</li><li>שאלות על חינוך פיננסי לילדים</li></ul>
        </aside>
      </div>
    </header>
    <section className={styles.section}><div className="container">
      <div className={styles.sectionHeader}><h2>כסף וזוגיות: שני צדדים של אותה שיחה</h2><p>לפעמים הוויכוח הוא על קנייה מסוימת, אבל מתחתיו נמצאות תחושות של אחריות, חופש, ביטחון או חלוקה לא הוגנת של העומס. ההתחלה היא לברר מה כל אחד צריך, ולא לחלק אשמה.</p></div>
      <div className={styles.cardGrid}>
        <article className={styles.card}><h3><FiHeart aria-hidden="true" /> ליווי כלכלי־זוגי</h3><p>יצירת מרחב לשיחה על כסף, בירור פערים בהוצאות ובחיסכון והגעה להסכמות שאפשר לבדוק שוב לאורך זמן.</p><Link to="/blog/money-fights-communication">איך להתמודד עם מריבות על כסף?</Link></article>
        <article className={styles.card}><h3><FiHome aria-hidden="true" /> תקציב והתנהלות בבית</h3><p>מיפוי הכנסות והוצאות, הבחנה בין קבוע למשתנה, קביעת סדרי עדיפויות ובניית הרגלי בדיקה רגועים.</p><Link to="/blog/category/family-finances">מדריכים לניהול תקציב משפחתי</Link></article>
        <article className={styles.card}><h3><FiUsers aria-hidden="true" /> חינוך פיננסי להורים</h3><p>שיחות מותאמות לגיל על דמי כיס, בחירות וקניות, בלי להעמיס על הילדים דאגות כלכליות של המבוגרים.</p><Link to="/services/parenting">עוד על הדרכת הורים</Link></article>
      </div>
    </div></section>
    <section className={styles.softSection}><div className="container">
      <div className={styles.sectionHeader}><h2>איך אפשר להתחיל?</h2><p>תהליך הליווי נקבע לפי צרכי המשפחה וההתאמה בשיחה הראשונית. אלה צעדים שניתן לבחון, לא תוכנית אחידה שמוכתבת מראש.</p></div>
      <div className={styles.processGrid}>
        <article className={styles.processStep}><h3>מגדירים מה חשוב</h3><p>מזהים את מוקדי הקושי ואת ההחלטה הראשונה שאותה רוצים לקבל אחרת.</p></article>
        <article className={styles.processStep}><h3>משרטטים תמונה מציאותית</h3><p>עושים סדר בהכנסות, הוצאות והרגלים, במידת הצורך ובאופן ששומר על פרטיות.</p></article>
        <article className={styles.processStep}><h3>מנסחים הסכמות</h3><p>בוחרים צעדים פשוטים, מחלקים אחריות ומחליטים מתי חוזרים לבדוק מה עובד.</p></article>
      </div>
      <div className={styles.highlight}><h2>מתי נכון לפנות לאיש מקצוע אחר?</h2><p>הליווי עוסק בחינוך פיננסי ובהתנהלות כלכלת הבית. הוא אינו ייעוץ השקעות, ייעוץ פנסיוני, ייעוץ מס, ייעוץ משפטי או הסדר חובות מקצועי. במצבים המצריכים שירות מפוקח או טיפול משפטי נדרשת פנייה לגורם המתאים. במצבים של כפייה או שליטה כלכלית בטיחות האדם קודמת לתרגילי תקציב משותפים.</p></div>
    </div></section>
    <section className={styles.section}><div className="container">
      <div className={styles.sectionHeader}><h2>תשובות לשאלות שכדאי לשאול</h2></div>
      <div className={styles.twoColumns}>
        <article className={styles.column}><h3>האם צריך להגיע יחד?</h3><p>לא תמיד. אפשר לברר בפנייה הראשונה מה מטרת הליווי ואם נכון לקיים שיחה פרטנית או זוגית, בהתאם לשירות המוצע ולנסיבות.</p><h3>האם צריך להגיע עם כל הנתונים הפיננסיים?</h3><p>לא בפנייה הראשונית. אין לשלוח מספרי חשבון, מסמכים או נתונים רגישים דרך הטופס.</p></article>
        <article className={styles.column}><h3>מה ההבדל בין חינוך פיננסי לייעוץ השקעות?</h3><p>חינוך פיננסי עוסק בהבנה, בהרגלים ובקבלת החלטות מושכלת בבית. המלצה פרטנית על ניירות ערך, מוצרים פנסיוניים או שירות אחר הכפוף לרישוי אינה חלק מהשירות המתואר כאן.</p><h3>אפשר להתחיל בשיחה על הנושא בלי להתחייב לתהליך?</h3><p>אפשר לפנות לבירור התאמה ולקבל מידע על אופן העבודה והאפשרויות הקיימות.</p></article>
      </div>
      <div className={styles.heroActions}><Link className={styles.primaryButton} to={SITE_CONFIG.links.appointment}>ליצירת קשר עם שירה</Link><Link to="/services/couples" className={styles.secondaryButton}>על ייעוץ זוגי</Link></div>
    </div></section>
    <section className={styles.softSection}><div className="container"><h2><FiBookOpen aria-hidden="true" /> לקריאה ולהעמקה</h2><p>אפשר להתחיל גם באופן עצמאי:</p><ul className={styles.plainList}><li><a href="/downloads/financial/money-conversation-worksheet.html">דף עבודה להדפסה: שיחת הכסף הזוגית</a></li><li><a href="/downloads/financial/family-budget-template.csv" download>הורדת גיליון תקציב משפחתי (CSV)</a></li><li><Link to="/blog/category/family-finances">מרכז המאמרים על כלכלת המשפחה</Link></li><li><Link to="/blog/money-fights-communication">איך מדברים על הוצאות בלי להיכנס לאותו ריב?</Link></li><li><Link to="/blog/marriage-prep-financial-expectations-2026-08-24">איך מדברים על כסף לפני החתונה?</Link></li><li><Link to="/services/premarital-first-year">ליווי זוגי לפני נישואים</Link></li></ul><p>שירה סהרוני היא מורה לחינוך פיננסי ועוסקת גם בייעוץ זוגי והדרכת הורים. <Link to="/about">עוד על שירה והגישה שלה</Link>.</p></div></section>
  </div>
);
export default FinancialGuidancePage;
