import React from 'react';
import { Link } from 'react-router-dom';
import posts from '../../data/postSummaries.json';
import { getImageDimensions } from '../../data/imageDimensions';
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
              {post.image && (
                <div className={styles.imageWrapper}>
                  <img
                    src={post.image}
                    alt={post.title}
                    className={styles.postImage}
                    loading="lazy"
                    {...getImageDimensions(post.image)}
                  />
                  <span className={styles.category}>{post.category}</span>
                </div>
              )}
              <div className={styles.content}>
                {!post.image && (
                  <span className={styles.categoryNoImage}>{post.category}</span>
                )}
                <h3 className={styles.postTitle}>{post.title}</h3>
                <p className={styles.excerpt}>{post.excerpt}</p>
                <Link to={`/blog/${post.id}`} className={styles.readMore} aria-label={`קרא עוד על ${post.title}`}>קרא עוד</Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
};

export default BlogPreview;
