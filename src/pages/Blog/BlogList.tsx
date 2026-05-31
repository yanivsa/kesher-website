import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { FiSearch, FiFilter } from 'react-icons/fi';
import posts from '../../data/posts.json';
import MetaTags from '../../components/SEO/MetaTags';
import styles from './BlogList.module.css';

const categories = ['הכל', 'זוגיות', 'הדרכת הורים', 'גישור משפחתי'];

const BlogList: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('הכל');

  const filteredPosts = useMemo(() => {
    return posts.filter(post => {
      const matchesSearch = post.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          post.excerpt.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory = activeCategory === 'הכל' || post.category === activeCategory;
      return matchesSearch && matchesCategory;
    });
  }, [searchQuery, activeCategory]);

  return (
    <div className={styles.blog}>
      <MetaTags 
        title="הבלוג של שירה סהרוני | ייעוץ זוגי, הדרכת הורים וגישור"
        description="מאמרים, טיפים ותובנות על זוגיות, הורות ופתרון סכסוכים. כל מה שצריך כדי לבנות מערכות יחסים טובות יותר."
      />
      <header className={styles.header}>
        <div className="container">
          <h1>הבלוג המקצועי</h1>
          <p>תובנות, כלים וסיפורים מהקליניקה וחדר הגישור.</p>
        </div>
      </header>

      <div className="container">
        <div className={styles.controls}>
          <div className={styles.searchWrapper}>
            <FiSearch className={styles.searchIcon} />
            <input 
              type="text" 
              placeholder="חיפוש מאמרים..." 
              aria-label="חיפוש מאמרים"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={styles.searchInput}
            />
          </div>
          <div className={styles.filterWrapper}>
            <FiFilter className={styles.filterIcon} />
            <div className={styles.categories}>
              {categories.map(cat => (
                <button 
                  key={cat}
                  className={`${styles.categoryBtn} ${activeCategory === cat ? styles.active : ''}`}
                  onClick={() => setActiveCategory(cat)}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>
        </div>

        {filteredPosts.length > 0 ? (
          <div className={styles.grid}>
            {filteredPosts.map((post) => (
              <article key={post.id} className={styles.card}>
                <div className={styles.imageWrapper}>
                  <img src={post.image} alt={post.title} className={styles.image} loading="lazy" />
                  <span className={styles.categoryBadge}>{post.category}</span>
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
        ) : (
          <div className={styles.noResults}>
            <h3>לא נמצאו מאמרים התואמים את החיפוש שלך.</h3>
            <button onClick={() => {setSearchQuery(''); setActiveCategory('הכל');}} className={styles.resetBtn}>נקה חיפוש</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default BlogList;
