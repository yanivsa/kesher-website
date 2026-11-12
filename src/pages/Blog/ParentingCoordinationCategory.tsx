import React from 'react';
import { Link } from 'react-router-dom';
import posts from '../../data/publishedPosts';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './ParentingCoordinationCategory.module.css';

const categoryPosts = posts.filter((post) => post.category === 'תיאום הורי');
const path = '/blog/category/parenting-coordination';
const url = SITE_CONFIG.url + path;
const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'CollectionPage',
      '@id': url + '#webpage',
      name: 'תיאום הורי — מדריכים ומאמרים',
      description: 'מאמרים מעשיים על תיאום הורי ותקשורת בין הורים לאחר פרידה.',
      url,
      isPartOf: { '@id': SITE_CONFIG.url + '/#website' },
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'עמוד הבית', item: SITE_CONFIG.url },
        { '@type': 'ListItem', position: 2, name: 'בלוג', item: SITE_CONFIG.url + '/blog' },
        { '@type': 'ListItem', position: 3, name: 'תיאום הורי', item: url },
      ],
    },
  ],
};

const ParentingCoordinationCategory: React.FC = () => (
  <div className={styles.page}>
    <MetaTags
      title="תיאום הורי: מאמרים ומדריכים להורים גרושים | שירה סהרוני"
      description="מדריכים מעשיים על תיאום הורי, מחלוקות בין הורים גרושים, תקשורת לאחר פרידה וזמני שהות, עם מקורות מקצועיים והפניה לשירות."
      canonical={url}
    />
    <SchemaOrg data={schemaData} />
    <header className={styles.hero}>
      <div className="container">
        <nav aria-label="נתיב ניווט" className={styles.breadcrumb}><Link to="/">עמוד הבית</Link> / <Link to="/blog">מאמרים</Link> / תיאום הורי</nav>
        <h1>תיאום הורי — מדריכים וכלים להורות לאחר פרידה</h1>
        <p>גם כאשר הקשר הזוגי הסתיים, החלטות הנוגעות לילדים ממשיכות להיות משותפות. כאן מרוכזים מדריכים על תקשורת בין הורים, יישוב מחלוקות ושמירה על מקומם של הילדים מחוץ למאבק.</p>
        <Link className={styles.button} to="/services/parenting-coordination">מהו תיאום הורי ומתי בודקים התאמה?</Link>
      </div>
    </header>
    <section className={'container ' + styles.section} aria-label="מאמרים בנושא תיאום הורי">
      <h2>מאמרים בנושא</h2>
      {categoryPosts.length === 0 ? (
        <p>מאמרים חדשים בנושא יפורסמו כאן בקרוב. בינתיים ניתן לקרוא על <Link to="/parenting-guidance-divorce">הדרכת הורים בתקופת פרידה</Link>.</p>
      ) : (
        <div className={styles.grid}>
          {categoryPosts.map((post) => (
            <article key={post.id} className={styles.card}>
              {post.image && <Link to={'/blog/' + post.id} aria-label={post.title}><img src={post.image} alt={post.imageAlt || post.title} width="800" height="500" loading="lazy" /></Link>}
              <div className={styles.cardContent}>
                <h3><Link to={'/blog/' + post.id}>{post.title}</Link></h3>
                <p>{post.excerpt}</p>
                <Link to={'/blog/' + post.id}>לקריאת המאמר</Link>
              </div>
            </article>
          ))}
        </div>
      )}
      <aside className={styles.next}>
        <h2>מתלבטים בין תיאום הורי להדרכת הורים?</h2>
        <p>חשוב להתאים את סוג הליווי למצב המשפחה, ולא להניח שכל מחלוקת מחייבת את אותו התהליך.</p>
        <Link to="/services/parenting-coordination">מידע על תיאום הורי</Link> · <Link to="/parenting-guidance-divorce">הדרכת הורים בגירושין</Link>
      </aside>
    </section>
  </div>
);

export default ParentingCoordinationCategory;
