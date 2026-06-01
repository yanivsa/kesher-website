import React from 'react';
import { Link } from 'react-router-dom';
import posts from '../../data/posts.json';
import styles from './BlogPreview.module.css';

// Get latest 3 posts
const latestPosts = [...posts]
  .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
  .slice(0, 3);

const BlogPreview: React.FC = () => {
  return (
    <section id="blog" className={styles.blog}>
      <div className="container">
        <div className={styles.header}>
          <h2 className={styles.title}>מהבלוג שלי</h2>
          <Link to="/blog" className={styles.viewAll}>לכל המאמרים ←</Link>
        </div>
        <div className={styles.grid}>
          {latestPosts.map((post) => (
            <article key={post.id} className={styles.card}>
              <div className={styles.imageWrapper}>
                <img src={post.image} alt={post.title} className={styles.postImage} />
                <span className={styles.category}>{post.category}</span>
              </div>
              <div className={styles.content}>
                <h3 className={styles.postTitle}>{post.title}</h3>
                <p className={styles.excerpt}>{post.excerpt}</p>
                <Link to={`/blog/${post.id}`} className={styles.readMore}>קרא עוד</Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
};

export default BlogPreview;
