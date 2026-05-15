import React from 'react';
import { Link } from 'react-router-dom';
import posts from '../../data/posts.json';
import MetaTags from '../../components/SEO/MetaTags';
import styles from './BlogList.module.css';

const BlogList: React.FC = () => {
  return (
    <div className={styles.blog}>
      <MetaTags 
        title="הבלוג של שירה סהרוני | ייעוץ זוגי, הדרכת הורים וגישור"
        description="מאמרים, טיפים ותובנות על זוגיות, הורות ופתרון סכסוכים. כל מה שצריך כדי לבנות מערכות יחסים טובות יותר."
      />
      <header className={styles.header}>
        <div className="container">
          <h1>הבלוג של שירה</h1>
          <p>תובנות וכלים פרקטיים לחיים זוגיים ומשפחתיים טובים יותר.</p>
        </div>
      </header>
      <div className="container">
        <div className={styles.grid}>
          {posts.map((post) => (
            <article key={post.id} className={styles.card}>
              <div className={styles.imageWrapper}>
                <img src={post.image} alt={post.title} className={styles.image} />
                <span className={styles.category}>{post.category}</span>
              </div>
              <div className={styles.content}>
                <span className={styles.date}>{new Date(post.date).toLocaleDateString('he-IL')}</span>
                <h2 className={styles.title}>{post.title}</h2>
                <p className={styles.excerpt}>{post.excerpt}</p>
                <Link to={`/blog/${post.id}`} className={styles.link}>קרא עוד ←</Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
};

export default BlogList;
