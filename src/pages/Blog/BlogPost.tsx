import React from 'react';
import { useParams, Link } from 'react-router-dom';
import posts from '../../data/posts.json';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import LeadMagnet from '../../components/LeadMagnet/LeadMagnet';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './BlogPost.module.css';

const BlogPost: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const post = posts.find(p => p.id === id);

  if (!post) {
    return (
      <div className="container">
        <h1>המאמר לא נמצא</h1>
        <Link to="/blog">חזרה לבלוג</Link>
      </div>
    );
  }

  const schemaData = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Article",
        "headline": post.title,
        "image": `${SITE_CONFIG.url}${post.image}`,
        "datePublished": post.date,
        "author": {
          "@type": "Person",
          "name": SITE_CONFIG.author,
          "url": SITE_CONFIG.url
        },
        "publisher": {
          "@type": "Organization",
          "name": SITE_CONFIG.brand,
          "logo": {
            "@type": "ImageObject",
            "url": `${SITE_CONFIG.url}/images/generated/site/logo.png`
          }
        },
        "description": post.excerpt
      },
      {
        "@type": "BreadcrumbList",
        "itemListElement": [
          {
            "@type": "ListItem",
            "position": 1,
            "name": "עמוד הבית",
            "item": SITE_CONFIG.url
          },
          {
            "@type": "ListItem",
            "position": 2,
            "name": "בלוג",
            "item": `${SITE_CONFIG.url}/blog`
          },
          {
            "@type": "ListItem",
            "position": 3,
            "name": post.title,
            "item": `${SITE_CONFIG.url}/blog/${post.id}`
          }
        ]
      }
    ]
  };

  return (
    <article className={styles.post}>
      <MetaTags title={post.title} description={post.excerpt} ogType="article" image={post.image} />
      <SchemaOrg data={schemaData} />
      <header className={styles.header}>
        <div className="container">
          <Link to="/blog" className={styles.backLink}>← חזרה לבלוג</Link>
          <span className={styles.category}>{post.category}</span>
          <h1 className={styles.title}>{post.title}</h1>
          <span className={styles.date}>{new Date(post.date).toLocaleDateString('he-IL')}</span>
        </div>
      </header>
      <div className={styles.imageWrapper}>
        <img src={post.image} alt={post.title} className={styles.image} />
      </div>
      <div className={`container ${styles.container}`}>
        <div className={styles.mainContent}>
          <div className={styles.content} dangerouslySetInnerHTML={{ __html: post.content }} />
          <LeadMagnet />
        </div>
        <aside className={styles.sidebar}>
          <div className={styles.ctaCard}>
            <h3>צריכים עזרה עם הנושא הזה?</h3>
            <p>אני כאן כדי ללוות אתכם בתהליך אישי ומותאם לכם.</p>
            <a href="/#contact" className={styles.ctaButton}>קביעת פגישת היכרות</a>
          </div>
        </aside>
      </div>
    </article>
  );
};

export default BlogPost;
