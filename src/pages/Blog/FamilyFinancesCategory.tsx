import React from 'react';
import { Link } from 'react-router-dom';
import posts from '../../data/publishedPosts';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './ParentingCoordinationCategory.module.css';

const legacy = new Set([
  'money-fights-communication',
  'marriage-preparation-money-fights',
  'marriage-prep-financial-expectations-2026-08-24',
]);
const categoryPosts = posts.filter(p => p.category === 'כלכלת המשפחה' || legacy.has(p.id));
const path = '/blog/category/family-finances';
const url = SITE_CONFIG.url + path;

const groupSpecs = [
  {
    id: 'finance-couples', title: 'כסף וזוגיות',
    description: 'מריבות על כסף, חלוקה הוגנת של הוצאות, סודות כלכליים והסכמות זוגיות.',
  },
  {
    id: 'finance-budget', title: 'תקציב משפחתי',
    description: 'מיפוי הכנסות והוצאות, תכנון שנתי ובניית תקציב שאפשר להתמיד בו.',
  },
  {
    id: 'finance-children', title: 'ילדים וכסף',
    description: 'דמי כיס, קניות וחינוך פיננסי שמתאים לגיל הילדים בלי להכביד עליהם.',
  },
  {
    id: 'finance-transitions', title: 'מעברים משפחתיים',
    description: 'שינויים בהכנסה, הרחבת המשפחה ותכנון מחדש כשנסיבות החיים משתנות.',
  },
];

const getPostGroup = (post: (typeof categoryPosts)[number]) =>
  legacy.has(post.id) ? 'כסף וזוגיות' : (post as { subcategory?: string }).subcategory;

const primaryGroups = groupSpecs.map(spec => ({
  ...spec,
  posts: categoryPosts.filter(post => getPostGroup(post) === spec.title),
}));
const listedIds = new Set(primaryGroups.flatMap(group => group.posts.map(post => post.id)));
const remainingPosts = categoryPosts.filter(post => !listedIds.has(post.id));
const groups = remainingPosts.length
  ? [...primaryGroups, {
      id: 'finance-more', title: 'נושאים נוספים',
      description: 'עוד מדריכים להתנהלות כלכלית במשפחה.',
      posts: remainingPosts,
    }]
  : primaryGroups;
const orderedPosts = groups.flatMap(group => group.posts);

const schemaData = { '@context': 'https://schema.org', '@graph': [
  { '@type': 'CollectionPage', '@id': url + '#webpage', name: 'כלכלת המשפחה — מדריכים מעשיים', url,
    inLanguage: 'he', isPartOf: { '@id': SITE_CONFIG.url + '/#website' },
    mainEntity: { '@type': 'ItemList', numberOfItems: orderedPosts.length,
      itemListElement: orderedPosts.map((p, i) => ({ '@type': 'ListItem', position: i + 1, name: p.title, url: SITE_CONFIG.url + '/blog/' + p.id })) }},
  { '@type': 'BreadcrumbList', itemListElement: [
    { '@type': 'ListItem', position: 1, name: 'עמוד הבית', item: SITE_CONFIG.url },
    { '@type': 'ListItem', position: 2, name: 'מאמרים', item: SITE_CONFIG.url + '/blog' },
    { '@type': 'ListItem', position: 3, name: 'כלכלת המשפחה', item: url } ] },
] };

const FamilyFinancesCategory: React.FC = () => (
  <div className={styles.page}>
    <MetaTags title="כלכלת המשפחה: כסף, זוגיות ותקציב" description="מדריכים וכלים לחינוך פיננסי במשפחה, שיח זוגי על כסף, בניית תקציב והתמודדות עם הוצאות. שירה סהרוני, אשדוד ובאונליין." canonical={url} image="/images/generated/site/home-hero.jpg" />
    <SchemaOrg data={schemaData} />
    <header className={styles.hero}><div className="container">
      <nav className={styles.breadcrumb} aria-label="נתיב ניווט"><Link to="/">עמוד הבית</Link> / <Link to="/blog">מאמרים</Link> / כלכלת המשפחה</nav>
      <h1>כלכלת המשפחה — כסף, זוגיות והורות בגובה העיניים</h1>
      <p><strong>כדי לעשות סדר בכסף כדאי להתחיל גם בשיחה על מה שחשוב בבית.</strong> כאן תמצאו מאמרים על תקציב משפחתי, על פערים בהרגלי הוצאה וחיסכון, על תיאום ציפיות ועל הדרך ללמד ילדים לנהל בחירות כלכליות בלי להעמיס עליהם דאגות של מבוגרים.</p>
      <Link className={styles.button} to="/services/family-financial-guidance">איך עובד ליווי כלכלי לזוגות ומשפחות?</Link>
    </div></header>
    <main className={'container ' + styles.section} aria-label="מאמרים על כלכלת המשפחה">
      <h2>במה רוצים להתמקד?</h2>
      <nav className={styles.financeTopics} aria-label="קפיצה לנושאים">
        {groups.map(group => <a href={'#' + group.id} key={group.id}>{group.title}<span aria-hidden="true"> ({group.posts.length})</span></a>)}
      </nav>
      {groups.map(group => (
        <section className={styles.financeGroup} key={group.id} id={group.id} aria-labelledby={group.id + '-title'}>
          <h2 id={group.id + '-title'}>{group.title}</h2>
          <p>{group.description}</p>
          <div className={styles.grid}>
            {group.posts.map(p => <article key={p.id} className={styles.card}>
              {p.image && <Link to={'/blog/' + p.id} aria-label={p.title}><img src={p.image} alt={p.imageAlt || p.title} width="800" height="500" loading="lazy" /></Link>}
              <div className={styles.cardContent}><h3><Link to={'/blog/' + p.id}>{p.title}</Link></h3><p>{p.excerpt}</p><Link to={'/blog/' + p.id}>לקריאת המאמר</Link></div>
            </article>)}
          </div>
        </section>
      ))}
      <section className={styles.next}>
        <h2>מתי נכון לפנות לליווי אישי?</h2>
        <p>אם הכנתם תקציב אבל מתקשים להתמיד בו, או כשכל שיחה על כסף הופכת לריב, אפשר לברר מה מתאים למשפחה שלכם. <Link to="/services/family-financial-guidance">מידע על הליווי הכלכלי</Link>.</p>
      </section>
      <p className={styles.sources}>המאמרים מציעים חינוך פיננסי וכלים כלליים; אינם מהווים המלצת השקעה, ייעוץ פנסיוני, ייעוץ משפטי או ייעוץ מס אישי.</p>
    </main>
  </div>
);

export default FamilyFinancesCategory;
