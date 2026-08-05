import React from 'react';
import { Link } from 'react-router-dom';
import {
  FiCalendar,
  FiDollarSign,
  FiHeart,
  FiHome,
  FiMessageCircle,
  FiRefreshCw,
  FiUsers,
} from 'react-icons/fi';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import ServiceFAQ from '../../../components/FAQ/ServiceFAQ';
import TherapistBio from '../../../components/TherapistBio/TherapistBio';
import faqs from '../../../data/faqs';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from '../shared/SpecialtyServicePage.module.css';

const faqCategory = 'הכנה לנישואים והשנה הראשונה';
const pageFaqs = faqs.filter((faq) => faq.category === faqCategory);
const blogHref = '/blog?category=זוגיות&subcategory=הכנה לנישואים והשנה הראשונה';

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Service',
      name: 'פגישות הכנה לנישואים וליווי בשנה הראשונה',
      serviceType: 'הכנה זוגית מעשית לפני החתונה וליווי לזוגות בתחילת הנישואים',
      url: `${SITE_CONFIG.url}/services/premarital-first-year`,
      provider: { '@type': 'LocalBusiness', '@id': `${SITE_CONFIG.url}/#business` },
      image: `${SITE_CONFIG.url}/images/generated/services/premarital-first-year.webp`,
      description: 'פגישות הכנה לנישואים וליווי בשנה הראשונה סביב כסף, בית, משפחות, אינטימיות, תקשורת, חלוקת אחריות ותיקון אחרי ריב.',
      areaServed: 'ישראל',
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'עמוד הבית', item: SITE_CONFIG.url },
        {
          '@type': 'ListItem',
          position: 2,
          name: 'הכנה לנישואים וליווי בשנה הראשונה',
          item: `${SITE_CONFIG.url}/services/premarital-first-year`,
        },
      ],
    },
    {
      '@type': 'FAQPage',
      mainEntity: pageFaqs.map((faq) => ({
        '@type': 'Question',
        name: faq.question,
        acceptedAnswer: { '@type': 'Answer', text: faq.answer },
      })),
    },
  ],
};

const PremaritalFirstYearPage: React.FC = () => (
  <div className={styles.page}>
    <MetaTags
      title="הכנה לנישואים וליווי בשנה הראשונה"
      description="פגישות הכנה לנישואים וליווי זוגי בשנה הראשונה: כסף, בית, משפחות, אינטימיות, חלוקת אחריות ותקשורת בזמן מחלוקת."
      image="/images/generated/services/premarital-first-year.webp"
    />
    <SchemaOrg data={schemaData} />

    <header className={styles.hero}>
      <div className={`container ${styles.heroGrid}`}>
        <div>
          <span className={styles.eyebrow}><FiHeart aria-hidden="true" /> לא רק להתכונן לחתונה — להתכונן לחיים יחד</span>
          <h1>הכנה לנישואים וליווי בשנה הראשונה</h1>
          <p className={styles.lead}>
            רוב הזוגות משקיעים חודשים בערב אחד, ואת החיים שאחריו לומדים תוך כדי. סדרת פגישות ממוקדת מאפשרת לדבר מראש על כסף, בית, משפחות, אינטימיות ומריבות — ולהמשיך לקבל ליווי כשההסכמות פוגשות את המציאות.
          </p>
          <div className={styles.heroActions}>
            <Link to={SITE_CONFIG.links.appointment} className={styles.primaryButton}>קביעת פגישת הכנה</Link>
            <Link to="/services/couples" className={styles.secondaryButton}>ייעוץ זוגי במצבי משבר</Link>
          </div>
        </div>
        <aside className={styles.heroPanel} aria-label="נושאים בהכנה לנישואים">
          <div className={styles.heroMedia}>
            <img
              src="/images/generated/services/premarital-first-year.webp"
              alt="זוג מאורס מנהל שיחת הכנה מעשית לקראת החיים המשותפים"
              width="1600"
              height="900"
              fetchPriority="high"
            />
          </div>
          <h2>מתאים גם לזוג שמסתדר מצוין</h2>
          <ul className={styles.checkList}>
            <li>לפני מגורים משותפים או לפני החתונה</li>
            <li>בחודשים הראשונים אחרי הנישואים</li>
            <li>כשאותה מחלוקת מתחילה לחזור</li>
            <li>לפני החלטה גדולה על כסף, בית או משפחה</li>
          </ul>
        </aside>
      </div>
    </header>

    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>שש שיחות שלא כדאי להשאיר ל״נסתדר כבר״</h2>
          <p>המטרה אינה להסכים על הכול. המטרה היא לדעת איפה אתם שונים, איך מקבלים החלטה ומה עושים כשהתוכנית משתנה.</p>
        </div>
        <div className={styles.cardGrid}>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiDollarSign aria-hidden="true" /></span>
            <h3>כסף</h3>
            <p>חשבונות משותפים או נפרדים, חובות, חיסכון, עזרה מההורים ומה נחשב הוצאה שצריך לתאם.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiHome aria-hidden="true" /></span>
            <h3>בית ואחריות</h3>
            <p>מי מחזיק את התמונה המלאה, איך מחלקים משימות ומה עושים כשאחד עמוס יותר לתקופה.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiMessageCircle aria-hidden="true" /></span>
            <h3>ריב ותיקון</h3>
            <p>איך עוצרים הסלמה, כמה זמן לוקחים להפסקה ואיך חוזרים לשיחה במקום לטאטא אותה.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiUsers aria-hidden="true" /></span>
            <h3>משפחות המוצא</h3>
            <p>שבתות וחגים, ביקורים, עצות, עזרה כלכלית והגבול שבין קרבה משפחתית להחלטה זוגית.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiHeart aria-hidden="true" /></span>
            <h3>קרבה ואינטימיות</h3>
            <p>איך מדברים על צורך, יוזמה, דחייה ועומס בלי להפוך את הנושא למדד לאהבה.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiCalendar aria-hidden="true" /></span>
            <h3>זמן ותוכניות</h3>
            <p>קריירה, חברים, זמן לבד, ילדים בעתיד והדרך לקבל החלטות כשהקצב של כל אחד שונה.</p>
          </article>
        </div>
      </div>
    </section>

    <section className={styles.softSection}>
      <div className="container">
        <div className={styles.twoColumns}>
          <article className={styles.column}>
            <span className={styles.cardIcon}><FiCalendar aria-hidden="true" /></span>
            <h3>לפני החתונה</h3>
            <p>סדרת פגישות ממוקדת שמתחילה במפת הציפיות של כל אחד וממשיכה לנושאים שחשוב להסדיר לפני שמתחילים את החיים המשותפים.</p>
            <ul className={styles.plainList}>
              <li>איתור פערים לפני שהם נהפכים להפתעה</li>
              <li>שיחות שאפשר לקיים בבית בין הפגישות</li>
              <li>הסכמות ברורות עם מקום לשינוי</li>
              <li>כללי בסיס לריב, הפסקה וחזרה לשיחה</li>
            </ul>
          </article>
          <article className={styles.column}>
            <span className={styles.cardIcon}><FiRefreshCw aria-hidden="true" /></span>
            <h3>בשנה הראשונה</h3>
            <p>פגישות לפי הצורך כשהתכנון פוגש שכר דירה, חשבונות, שתי משפחות, לוחות זמנים והרגלים שלא הכרתם עד הסוף.</p>
            <ul className={styles.plainList}>
              <li>בדיקת ההסכמות מול מה שקורה בפועל</li>
              <li>שינוי חלוקת תפקידים בלי פנקסנות</li>
              <li>תיקון דפוס לפני שהוא מתקבע</li>
              <li>שמירה על זוגיות לצד כל הלוגיסטיקה</li>
            </ul>
          </article>
        </div>
      </div>
    </section>

    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>איך נראה התהליך?</h2>
          <p>לא עוברים על שאלון כללי ומסמנים וי. בוחרים את הנושאים הרלוונטיים לכם, מתרגלים שיחה ובודקים איך היא מחזיקה בבית.</p>
        </div>
        <div className={styles.processGrid}>
          <article className={styles.processStep}><h3>ממפים ציפיות</h3><p>כל אחד מנסח איך הוא מדמיין כסף, בית, משפחה, זמן וקבלת החלטות — גם בדברים שנראו מובנים מאליהם.</p></article>
          <article className={styles.processStep}><h3>בונים הסכמות</h3><p>מנסחים כללים קצרים ומעשיים: מי אחראי, מתי מדברים ואיך יודעים שצריך לעדכן את ההסכמה.</p></article>
          <article className={styles.processStep}><h3>מתרגלים תיקון</h3><p>לומדים לזהות את רגע ההסלמה, לעצור בלי להיעלם ולחזור עם בקשה שאפשר להבין ולבדוק.</p></article>
        </div>
      </div>
    </section>

    <section className={styles.softSection}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>מדריכים שכדאי לקרוא ולשמור</h2>
          <p>שאלות, תרגילים ושיחות ביתיות לזוגות לפני החתונה ובתחילת הנישואים.</p>
        </div>
        <div className={styles.articleLinks}>
          <Link to="/blog/premarital-questions-before-wedding" className={styles.articleLink}>
            <strong>לפני שאומרים כן: 12 שאלות שחייבים לשאול לפני החתונה</strong>
            <span>כסף, משפחות, בית, קריירה, אינטימיות ומה עושים בזמן ריב.</span>
          </Link>
          <Link to="/blog/newlywed-first-year-conflicts" className={styles.articleLink}>
            <strong>השנה הראשונה לנישואים: 8 מריבות שמפתיעות זוגות טובים</strong>
            <span>איך לזהות מה באמת מסתתר מאחורי הוויכוח ואיך מתקנים.</span>
          </Link>
        </div>
        <div className={styles.heroActions}>
          <Link to={blogHref} className={styles.secondaryButton}>כל המאמרים על הכנה לנישואים והשנה הראשונה</Link>
        </div>
      </div>
    </section>

    <ServiceFAQ category={faqCategory} />

      <TherapistBio />


    <section className={styles.cta}>
      <div className="container">
        <h2>החתונה היא תאריך. הזוגיות היא מה שבונים אחריו</h2>
        <p>אפשר לקיים את הפגישות באשדוד או אונליין.</p>
        <Link to={SITE_CONFIG.links.appointment} className={styles.primaryButton}>בחירת מועד לפגישה</Link>
      </div>
    </section>
  </div>
);

export default PremaritalFirstYearPage;
