import React from 'react';
import { Link } from 'react-router-dom';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import { useLandingPageAnalytics } from '../../../hooks/useLandingPageAnalytics';
import styles from '../../Services/shared/SpecialtyServicePage.module.css';
type Mode = 'couples' | 'family';
interface Props { mode: Mode }
const config = {
  couples: {
    path: '/financial-guidance-couples', title: 'ליווי כלכלי לזוגות: לדבר על כסף בלי להיתקע באותו ריב',
    description: 'שיחות על הוצאות, חיסכון וחלוקת אחריות הפכו למקור מתח? ליווי כלכלי־זוגי בגישה מעשית לשיח, תכנון והסכמות.',
    lead: 'כשהאחד מבקש לחסוך והשנייה רוצה יותר חופש בקניות, הוויכוח הוא לא רק על הסכום. אפשר להבין מה חשוב לכל אחד ולנסח יחד הסכמות שניתן ליישם בבית.',
    image: '/images/financial-guidance/money-conversation.svg',
    points: ['מחלוקות חוזרות סביב קניות והוצאות', 'פערי גישה לתכנון ולחיסכון', 'קושי לדבר על כסף בלי האשמות'],
    steps: [['מבינים את המעגל', 'מתבוננים ברגעים שבהם השיחה על כסף מיד מתלקחת.'], ['מבהירים צרכים', 'מזהים איזה צורך מסתתר מאחורי עמדה שנראית נוקשה.'], ['בונים הסכמות', 'מתנסים בהחלטות קטנות ואפשריות ובודקים אותן יחד.']],
  },
  family: {
    path: '/family-budget-guidance', title: 'ליווי לניהול תקציב משפחתי — לבנות שגרה שאפשר לקיים',
    description: 'מרגישים שההוצאות מפתיעות בכל חודש? ליווי למשפחות במיפוי הוצאות, קביעת סדרי עדיפויות והרגלי תקציב לצד תקשורת משפחתית.',
    lead: 'החשבונות מגיעים, ההוצאות הקטנות מצטברות, ושוב קשה לדעת לאן הלך הכסף. אפשר להתחיל ממיפוי פשוט, להחליט מה חשוב ולבנות דרך מעשית לבדוק את ההוצאות יחד.',
    image: '/images/financial-guidance/family-budget.svg',
    points: ['לא ברור לאן נעלם הכסף במהלך החודש', 'קשה להתכונן להוצאות שנתיות', 'אין זמן או הסכמה לקיים שיחת תקציב'],
    steps: [['עושים סדר', 'ממפים בהדרגה הכנסות והוצאות בלי האשמות.'], ['מחליטים מה קודם', 'מבחינים בין הוצאות מחייבות לבחירות שאפשר לתכנן.'], ['יוצרים שגרה', 'בוחרים זמן קבוע לבדיקה ושינויים בהתאם למציאות.']],
  },
} as const;
const FinancialLandingPage: React.FC<Props> = ({mode}) => {
  const data = config[mode];
  const url = SITE_CONFIG.url + data.path;
  const { trackCtaClick, trackWhatsappClick } = useLandingPageAnalytics({landingPagePath:data.path, landingPageType:mode, serviceType:'family_financial_guidance'});
  return <div className={styles.page}>
    <MetaTags title={data.title} description={data.description} canonical={url} image={data.image} robots="noindex, follow" />
    <SchemaOrg data={{'@context':'https://schema.org','@graph':[
      {'@type':'Service','@id':url+'#service',name:data.title,description:data.description,provider:{'@id':SITE_CONFIG.url+'/#business'},areaServed:'ישראל',url},
      {'@type':'BreadcrumbList',itemListElement:[{'@type':'ListItem',position:1,name:'עמוד הבית',item:SITE_CONFIG.url},{'@type':'ListItem',position:2,name:data.title,item:url}]}]}} />
    <header className={styles.hero}><div className={\`container \${styles.heroGrid}\`}>
      <div><h1>{data.title}</h1><p className={styles.lead}>{data.lead}</p>
        <div className={styles.heroActions}><Link className={styles.primaryButton} to={SITE_CONFIG.links.appointment} onClick={()=>trackCtaClick('קביעת פגישה','hero')}>בירור התאמה עם שירה</Link><a className={styles.secondaryButton} href={SITE_CONFIG.links.whatsapp} onClick={()=>trackWhatsappClick('hero')} rel="noopener noreferrer">שליחת הודעה בוואטסאפ</a></div>
      </div>
      <aside className={styles.heroPanel}><div className={styles.heroMedia}><img src={data.image} alt={mode==='couples'?'איור שיחה זוגית לצד מחברת ותקציב':'איור חלוקת הוצאות ביתיות על דף תקציב'} width="1200" height="675" fetchPriority="high" /></div><h2>מתי כדאי לברר התאמה?</h2><ul className={styles.checkList}>{data.points.map(p=><li key={p}>{p}</li>)}</ul></aside>
    </div></header>
    <section className={styles.section}><div className="container"><h2>מה אפשר לבדוק יחד בתהליך?</h2><div className={styles.processGrid}>{data.steps.map(([title,desc])=><article className={styles.processStep} key={title}><h3>{title}</h3><p>{desc}</p></article>)}</div></div></section>
    <section className={styles.softSection}><div className="container">
      <h2>כדאי לדעת לפני שפונים</h2><p>הליווי עוסק בחינוך פיננסי ובהתנהלות כלכלת הבית לצד תקשורת זוגית ומשפחתית. הוא אינו תחליף לייעוץ השקעות, פנסיה, מס או משפט. בפנייה הראשונה אין לשלוח מידע פיננסי רגיש.</p>
      <p>אפשר לברר אפשרות לפגישה באשדוד או אונליין בהתאם לזמינות ולתיאום מראש. <Link to="/services/family-financial-guidance">קראו על השירות המלא</Link> או <Link to="/blog/category/family-finances">בקרו במרכז המאמרים</Link>.</p>
      <div className={styles.heroActions}><Link className={styles.primaryButton} to={SITE_CONFIG.links.appointment} onClick={()=>trackCtaClick('קביעת פגישה','footer')}>קביעת פגישת היכרות</Link></div>
    </div></section>
  </div>;
};
export default FinancialLandingPage;
