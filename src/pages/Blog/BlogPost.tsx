import React, { useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import DOMPurify from 'dompurify';
import posts from '../../data/publishedPosts';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import LeadMagnet from '../../components/LeadMagnet/LeadMagnet';
import { SITE_CONFIG } from '../../constants/siteConfig';
import { getImageDimensions } from '../../data/imageDimensions';
import styles from './BlogPost.module.css';

const BlogPost: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const post = posts.find(p => p.id === id);



  const schemaData = useMemo(() => ({
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Article",
        "headline": post?.title || "",
        "image": `${SITE_CONFIG.url}${post?.image || ""}`,
        "url": `${SITE_CONFIG.url}/blog/${post?.id || ""}`,
        "datePublished": post?.date || "",
        "dateModified": post?.date || "",
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
            "url": `${SITE_CONFIG.url}/apple-touch-icon.png`
          }
        },
        "description": post?.excerpt || "",
        "articleBody": post?.content?.replace(/<[^>]+>/g, ' ') || ""
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
            "name": post?.title || "",
            "item": `${SITE_CONFIG.url}/blog/${post?.id || ""}`
          }
        ]
      }
    ]
  }), [post?.title, post?.image, post?.id, post?.date, post?.excerpt, post?.content]);

  if (!post) {
    return (
      <div className="container">
        <h1>המאמר לא נמצא</h1>
        <Link to="/blog">חזרה לבלוג</Link>
      </div>
    );
  }
  const safeContent = DOMPurify.sanitize(post.content);

  return (
    <article className={styles.post}>
      <MetaTags title={`${post.title} | ${SITE_CONFIG.brand}`} description={post.excerpt} ogType="article" image={post.image} />
      <SchemaOrg data={schemaData} />
      <header className={styles.header}>
        <div className="container">
          <Link to="/blog" className={styles.backLink}>← חזרה לבלוג</Link>
          <span className={styles.category}>{post.category}</span>
          <h1 className={styles.title}>{post.title}</h1>
          <span className={styles.date}>{new Date(post.date).toLocaleDateString('he-IL')}</span>
        </div>
      </header>
      <div className={`container ${styles.container}`}>
        <div className={styles.mainContent}>
          <div className={styles.imageWrapper}>
            <img
              src={post.image}
              alt={post.title}
              className={styles.image}
              fetchPriority="high"
              {...getImageDimensions(post.image)}
            />
          </div>
          <div className={styles.content} dangerouslySetInnerHTML={{ __html: safeContent }} />
          <p className={styles.disclaimer}>המאמר מספק מידע כללי ואינו מחליף ייעוץ מקצועי המותאם למצב האישי או המשפחתי.</p>
          <LeadMagnet />
        </div>
        <aside className={styles.sidebar}>
          <div className={styles.ctaCard}>
            <h3>צריכים עזרה עם הנושא הזה?</h3>
            <p>אני כאן כדי ללוות אתכם בתהליך אישי ומותאם לכם.</p>
            <Link to="/contact" className={styles.ctaButton}>קביעת פגישת היכרות</Link>
          </div>
        </aside>
      </div>
    </article>
  );
};

export default BlogPost;
