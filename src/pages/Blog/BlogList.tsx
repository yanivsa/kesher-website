import React, { useState, useMemo, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { FiSearch, FiFilter } from 'react-icons/fi';
import posts from '../../data/posts.json';
import Fuse from 'fuse.js';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './BlogList.module.css';

const categories = ['הכל', 'זוגיות', 'הדרכת הורים', 'גישור משפחתי'];

const subcategories: Record<string, string[]> = {
  'זוגיות': ['הכל', 'הכנה לחתונה'],
  'הדרכת הורים': ['הכל', "הכנה לכיתה א' ו-ADHD"]
};

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Blog",
      "name": "הבלוג של שירה סהרוני | ייעוץ זוגי, הדרכת הורים וגישור",
      "description": "מאמרים, טיפים ותובנות על זוגיות, הורות ופתרון סכסוכים. כל מה שצריך כדי לבנות מערכות יחסים טובות יותר.",
      "url": `${SITE_CONFIG.url}/blog`,
      "publisher": {
        "@type": "Organization",
        "name": SITE_CONFIG.brand,
        "logo": {
          "@type": "ImageObject",
          "url": `${SITE_CONFIG.url}/apple-touch-icon.png`
        }
      },
      "blogPost": posts.slice(0, 5).map(post => ({
        "@type": "BlogPosting",
        "headline": post.title,
        "url": `${SITE_CONFIG.url}/blog/${post.id}`,
        "datePublished": post.date,
        "author": {
          "@type": "Person",
          "name": SITE_CONFIG.author
        }
      }))
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
        }
      ]
    }
  ]
};

const BlogList: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState(searchParams.get('category') || 'הכל');
  const [activeSubcategory, setActiveSubcategory] = useState(searchParams.get('subcategory') || 'הכל');

  useEffect(() => {
    setActiveCategory(searchParams.get('category') || 'הכל');
    setActiveSubcategory(searchParams.get('subcategory') || 'הכל');
  }, [searchParams]);

  const handleCategoryChange = (category: string) => {
    setSearchParams(category === 'הכל' ? {} : { category });
  };

  const handleSubcategoryChange = (subcategory: string) => {
    const params: Record<string, string> = {};
    if (activeCategory !== 'הכל') params.category = activeCategory;
    if (subcategory !== 'הכל') params.subcategory = subcategory;
    setSearchParams(params);
  };

  const fuse = useMemo(() => new Fuse(posts, {
    keys: ['title', 'excerpt'],
    threshold: 0.3,
  }), []);

  const filteredPosts = useMemo(() => {
    let result = posts;
    if (searchQuery) {
      result = fuse.search(searchQuery).map(res => res.item);
    }
    if (activeCategory !== 'הכל') {
      result = result.filter(post => post.category === activeCategory);
    }
    if (activeSubcategory !== 'הכל') {
      result = result.filter(post => 'subcategory' in post && post.subcategory === activeSubcategory);
    }
    return result;
  }, [searchQuery, activeCategory, activeSubcategory, fuse]);

  const resetFilters = () => {
    setSearchQuery('');
    setSearchParams({});
  };

  return (
    <div className={styles.blog}>
      <SchemaOrg data={schemaData} />
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
                  type="button"
                  key={cat}
                  className={`${styles.categoryBtn} ${activeCategory === cat ? styles.active : ''}`}
                  onClick={() => handleCategoryChange(cat)}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>
          {subcategories[activeCategory] && (
            <div className={styles.subcategoryRow}>
              <span>תחום התמחות:</span>
              <div className={styles.categories}>
                {subcategories[activeCategory].map(subcategory => (
                  <button
                    type="button"
                    key={subcategory}
                    className={`${styles.categoryBtn} ${activeSubcategory === subcategory ? styles.active : ''}`}
                    onClick={() => handleSubcategoryChange(subcategory)}
                  >
                    {subcategory}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {filteredPosts.length > 0 ? (
          <div className={styles.grid}>
            {filteredPosts.map((post) => (
              <article key={post.id} className={styles.card}>
                <div className={styles.imageWrapper}>
                  <img src={post.image} alt={post.title} className={styles.image} loading="lazy" />
                  <span className={styles.categoryBadge}>
                    {('subcategory' in post && post.subcategory) ? post.subcategory : post.category}
                  </span>
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
            <button type="button" onClick={resetFilters} className={styles.resetBtn}>נקה חיפוש</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default BlogList;
