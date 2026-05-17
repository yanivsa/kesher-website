import React from 'react';
import { useParams, Link } from 'react-router-dom';
import posts from '../../data/posts.json';
import MetaTags from '../../components/SEO/MetaTags';
import LeadMagnet from '../../components/LeadMagnet/LeadMagnet';
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

  return (
    <article className={styles.post}>
      <MetaTags title={post.title} description={post.excerpt} />
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
