import React from 'react';
import { Link } from 'react-router-dom';
import {
  FiBriefcase,
  FiCompass,
  FiDollarSign,
  FiGlobe,
  FiHeart,
  FiHome,
  FiUsers,
} from 'react-icons/fi';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import ServiceFAQ from '../../../components/FAQ/ServiceFAQ';
import faqs from '../../../data/faqs';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import styles from '../shared/SpecialtyServicePage.module.css';

const faqCategory = 'זוגיות בעלייה ורילוקיישן';
const pageFaqs = faqs.filter((faq) => faq.category === faqCategory);
const blogHref = '/blog?category=זוגיות&subcategory=זוגיות בעלייה ורילוקיישן';

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Service',
      name: 'ייעוץ זוגי לעולים ולזוגות ברילוקיישן',
      serviceType: 'ייעוץ זוגי לפני עלייה או רילוקיישן, בתקופת ההסתגלות ולאחר החזרה',
      url: `${SITE_CONFIG.url}/services/couples-aliyah-relocation`,
      provider: { '@type': 'LocalBusiness', '@id': `${SITE_CONFIG.url}/#business` },
      image: `${SITE_CONFIG.url}/images/generated/services/couples-aliyah-relocation.webp`,
      description: 'ייעוץ זוגי לעולים, לתושבים חוזרים ולזוגות לפני רילוקיישן או במהלכו, סביב פערי הסתגלות, שינוי תפקידים, כסף, שייכות ורשת תמיכה.',
      areaServed: 'אונליין',
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'עמוד הבית', item: SITE_CONFIG.url },
        {
          '@type': 'ListItem',
          position: 2,
          name: 'ייעוץ זוגי לעולים ולזוגות ברילוקיישן',
          item: `${SITE_CONFIG.url}/services/couples-aliyah-relocation`,
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

const CouplesAliyahRelocationPage: React.FC = () => (
  <div className={styles.page}>
    <MetaTags
      title="ייעוץ זוגי לעולים ולזוגות ברילוקיישן"
      description="ייעוץ זוגי לפני עלייה או רילוקיישן, בתקופת ההסתגלות ולאחר החזרה: תפקידים, כסף, בדידות, שייכות ותקשורת זוגית."
      image="/images/generated/services/couples-aliyah-relocation.webp"
    />
    <SchemaOrg data={schemaData} />

    <header className={styles.hero}>
      <div className={`container ${styles.heroGrid}`}>
        <div>
          <span className={styles.eyebrow}><FiGlobe aria-hidden="true" /> זוגיות כשהכתובת משתנה</span>
          <h1>ייעוץ זוגי לעולים ולזוגות ברילוקיישן</h1>
          <p className={styles.lead}>
            מעבר למדינה חדשה משנה יותר מהכתובת. הוא יכול לשנות מי עובד, מי תלוי במי, מי כבר מרגיש בבית ומי עדיין מתגעגע. בייעוץ נותנים מקום לשני הסיפורים ובונים הסכמות שמתאימות לחיים החדשים — לפני המעבר, במהלכו או אחרי החזרה.
          </p>
          <div className={styles.heroActions}>
            <Link to={SITE_CONFIG.links.appointment} className={styles.primaryButton}>קביעת פגישה זוגית</Link>
            <Link to="/services/aliyah-families" className={styles.secondaryButton}>ליווי הורי למשפחות עולים</Link>
          </div>
        </div>
        <aside className={styles.heroPanel} aria-label="נושאים בייעוץ זוגי סביב עלייה ורילוקיישן">
          <div className={styles.heroMedia}>
            <img
              src="/images/generated/services/couples-aliyah-relocation.webp"
              alt="בני זוג מתכננים יחד מעבר למדינה חדשה"
              width="1600"
              height="900"
              fetchPriority="high"
            />
          </div>
          <h2>אפשר להגיע גם כשהמעבר רצוי</h2>
          <ul className={styles.checkList}>
            <li>לפני ההחלטה או לפני האריזה</li>
            <li>בחודשים הראשונים במדינה החדשה</li>
            <li>כשאחד מסתגל והשני נשאר מאחור</li>
            <li>לקראת חזרה לישראל או אחריה</li>
          </ul>
        </aside>
      </div>
    </header>

    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>למה מעבר מדינה נכנס ישר לתוך הזוגיות?</h2>
          <p>גם זוג מתואם יכול לגלות שהחלוקה הישנה כבר לא עובדת. במקום להתווכח מי מקריב יותר, ממפים מה השתנה ומה כל אחד צריך עכשיו.</p>
        </div>
        <div className={styles.cardGrid}>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiBriefcase aria-hidden="true" /></span>
            <h3>קריירה ותלות</h3>
            <p>אחד מתקדם בעבודה והשני מחכה לאישור, לשפה או להזדמנות. בונים דרך לדבר על הכוח והמחיר בלי להקטין את התרומה של אף אחד.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiCompass aria-hidden="true" /></span>
            <h3>פער בקצב ההסתגלות</h3>
            <p>אחד כבר מכיר אנשים ומסתדר, והשני עדיין מרגיש אורח. לא דורשים קצב אחיד; מגדירים תמיכה ועצמאות לכל אחד.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiDollarSign aria-hidden="true" /></span>
            <h3>כסף ושליטה</h3>
            <p>הוצאות המעבר, חשבון חדש או משכורת אחת יכולים לשנות את מאזן הכוחות. הופכים את המספרים לשיחה משותפת ולא לכלי לחץ.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiUsers aria-hidden="true" /></span>
            <h3>בלי רשת התמיכה</h3>
            <p>כשהמשפחה והחברים רחוקים, בני הזוג נהפכים כמעט לכל העולם זה של זה. בונים קשרים ועוגנים מחוץ לזוגיות כדי להוריד עומס.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiHome aria-hidden="true" /></span>
            <h3>בית, שפה ותרבות</h3>
            <p>מה שנחשב ברור בארץ אחת יכול להרגיש מוזר באחרת. מדברים על מנהגים, שייכות וזהות בלי להפוך כל הבדל למבחן נאמנות.</p>
          </article>
          <article className={styles.card}>
            <span className={styles.cardIcon}><FiHeart aria-hidden="true" /></span>
            <h3>געגוע וספק</h3>
            <p>אפשר להתגעגע בלי להודיע שהמעבר נכשל. נותנים מקום לאמביוולנטיות ובודקים מה חסר ומה אפשר לשנות במציאות.</p>
          </article>
        </div>
      </div>
    </section>

    <section className={styles.softSection}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>מה עושים בפגישות?</h2>
          <p>הייעוץ נשען על מצבים אמיתיים מהשבוע שלכם ומתרגם אותם לשיחה, חלוקת אחריות או החלטה שאפשר לנסות.</p>
        </div>
        <div className={styles.processGrid}>
          <article className={styles.processStep}><h3>מציירים את מפת המעבר</h3><p>מי יזם, מה כל אחד מרוויח ומאבד, אילו החלטות כבר התקבלו ואיפה עדיין אין הסכמה.</p></article>
          <article className={styles.processStep}><h3>מנסחים חוזה זמני</h3><p>קובעים חלוקת אחריות, תקציב, זמן אישי ועוגנים זוגיים לתקופה שבה הכול עוד זז.</p></article>
          <article className={styles.processStep}><h3>בודקים את הפערים</h3><p>חוזרים למה שקרה בפועל, מזהים עומס חדש ומעדכנים את ההסכמות בלי להפוך שינוי לכישלון.</p></article>
        </div>
        <p className={styles.note}>
          הייעוץ מתמקד בקשר הזוגי ובהסתגלות הרגשית והמשפחתית. שאלות של אשרות, מסים, זכויות או תעסוקה דורשות בעל מקצוע מתאים בתחום.
        </p>
      </div>
    </section>

    <section className={styles.section}>
      <div className="container">
        <div className={styles.sectionHeader}>
          <h2>מדריכים פרקטיים לזוגות בתנועה</h2>
          <p>שיחות וצ׳ק־ליסטים שאפשר להתחיל מהם כבר הערב.</p>
        </div>
        <div className={styles.articleLinks}>
          <Link to="/blog/relocation-couple-conversations-before-moving" className={styles.articleLink}>
            <strong>רילוקיישן זוגי: 7 שיחות שחייבים לעשות לפני שאורזים</strong>
            <span>מתפקידים וכסף ועד ביקורים, קריירה ותוכנית יציאה.</span>
          </Link>
          <Link to="/blog/aliyah-partners-different-adjustment-pace" className={styles.articleLink}>
            <strong>אחד כבר בבית והשני עדיין אורח</strong>
            <span>מה עושים כשבני זוג מסתגלים לישראל בקצב שונה.</span>
          </Link>
        </div>
        <div className={styles.heroActions}>
          <Link to={blogHref} className={styles.secondaryButton}>כל המאמרים על זוגיות בעלייה ורילוקיישן</Link>
        </div>
      </div>
    </section>

    <ServiceFAQ category={faqCategory} />

    <section className={styles.cta}>
      <div className="container">
        <h2>אפשר לעבור מדינה בלי להשאיר את הזוגיות מאחור</h2>
        <p>הפגישות מתקיימות אונליין, וגם באשדוד למי שנמצאים בישראל.</p>
        <Link to={SITE_CONFIG.links.appointment} className={styles.primaryButton}>בחירת מועד לפגישה</Link>
      </div>
    </section>
  </div>
);

export default CouplesAliyahRelocationPage;
