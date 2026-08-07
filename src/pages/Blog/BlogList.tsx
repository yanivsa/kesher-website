import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import posts from '../../data/postSummaries.json';
import { getImageDimensions } from '../../data/imageDimensions';
import styles from './BlogList.module.css';

// Extract unique categories from actual posts data
const CATEGORIES = ['הכל', ...Array.from(new Set(posts.map(p => p.category)))];

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Blog",
      "@id": `${SITE_CONFIG.url}/blog/#blog`,
      "url": `${SITE_CONFIG.url}/blog`,
      "name": "מאמרים וקריאה מעשירה",
      "description": "מאמרים מקצועיים, תובנות וכלים מעשיים בנושאי ייעוץ זוגי, הדרכת הורים, תקשורת, גבולות ופתרון מחלוקות במשפחה.",
      "publisher": {
        "@id": `${SITE_CONFIG.url}/#business`
      }
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
  const [selectedCategory, setSelectedCategory] = useState('הכל');
  const [searchQuery, setSearchQuery] = useState('');

  // Combine categories and subcategories for filter tags
  const subcategoriesMap = useMemo(() => {
    const map = new Map<string, Set<string>>();
    posts.forEach(p => {
      if ('subcategory' in p && p.subcategory) {
        if (!map.has(p.category)) {
          map.set(p.category, new Set());
        }
        map.get(p.category)!.add(p.subcategory);
      }
    });
    return map;
  }, []);

  const filteredPosts = useMemo(() => {
    return posts.filter((post) => {
      const matchesCategory =
        selectedCategory === 'הכל' ||
        post.category === selectedCategory ||
        (('subcategory' in post && post.subcategory) ? post.subcategory === selectedCategory : false);

      const matchesSearch =
        searchQuery.trim() === '' ||
        post.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        post.excerpt.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (('subcategory' in post && post.subcategory) ? post.subcategory.toLowerCase().includes(searchQuery.toLowerCase()) : false);

      return matchesCategory && matchesSearch;
    });
  }, [selectedCategory, searchQuery]);

  return (
    <div className={styles.page}>
      <MetaTags
        title="מאמרים וקריאה מעשירה | שירה סהרוני — ייעוץ זוגי והדרכת הורים"
        description="מאמרים מקצועיים, תובנות וכלים מעשיים בנושאי ייעוץ זוגי, הדרכת הורים, תקשורת, גבולות ופתרון מחלוקות במשפחה. שירה סהרוני, אשדוד."
        canonical={`${SITE_CONFIG.url}/blog`}
      />
      <SchemaOrg data={schemaData} />

      <main className={styles.main}>
        {/* Header Section */}
        <header className={styles.header}>
          <div className={styles.headerContent}>
            <span className={styles.kicker}>תובנות וכלים מהקליניקה</span>
            <h1 className={styles.title}>מאמרים וקריאה מעשירה</h1>
            <p className={styles.subtitle}>
              מחשבות, נקודות למחשבה וכלים מעשיים לחיים זוגיים ומשפחתיים שמחים ורגועים יותר.
            </p>
          </div>
        </header>

        {/* Search Bar */}
        <div className={styles.searchSection}>
          <div className={styles.searchWrapper}>
            <span className={styles.searchIcon} aria-hidden="true">🔍</span>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="חפשי מאמר לפי נושא, מילת מפתח או תחום..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              aria-label="חיפוש מאמרים"
            />
            {searchQuery && (
              <button
                type="button"
                className={styles.clearSearch}
                onClick={() => setSearchQuery('')}
                aria-label="ניקוי חיפוש"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* Filter Categories */}
        <div className={styles.filterSection}>
          <div className={styles.categoriesContainer} role="tablist" aria-label="סינון לפי נושא">
            {CATEGORIES.map((category) => (
              <React.Fragment key={category}>
                <button
                  type="button"
                  role="tab"
                  aria-selected={selectedCategory === category}
                  className={`${styles.categoryTab} ${selectedCategory === category ? styles.activeTab : ''}`}
                  onClick={() => setSelectedCategory(category)}
                >
                  {category}
                </button>

                {/* Render subcategories inline if parent category is selected */}
                {selectedCategory === category && subcategoriesMap.has(category) && (
                  Array.from(subcategoriesMap.get(category)!).map(sub => (
                    <button
                      key={sub}
                      type="button"
                      role="tab"
                      aria-selected={selectedCategory === sub}
                      className={`${styles.categoryTab} ${styles.subcategoryTab} ${selectedCategory === sub ? styles.activeTab : ''}`}
                      onClick={() => setSelectedCategory(sub)}
                    >
                      {sub}
                    </button>
                  ))
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Articles Grid */}
        <div className={styles.postsSummary}>
          <span>
            {filteredPosts.length === posts.length
              ? `מציג את כל ${posts.length} המאמרים`
              : `נמצאו ${filteredPosts.length} מאמרים`}
          </span>
          {(selectedCategory !== 'הכל' || searchQuery) && (
            <button
              type="button"
              className={styles.resetFilters}
              onClick={() => {
                setSelectedCategory('הכל');
                setSearchQuery('');
              }}
            >
              איפוס סינונים
            </button>
          )}
        </div>

        {filteredPosts.length > 0 ? (
          <div className={styles.grid}>
            {filteredPosts.map((post) => (
              <article key={post.id} className={styles.card}>
                {post.image && (
                  <Link to={`/blog/${post.id}`} className={styles.imageLink} aria-label={post.title}>
                    <div className={styles.imageWrapper}>
                      <img
                        src={post.image}
                        alt={('imageAlt' in post && typeof post.imageAlt === 'string') ? post.imageAlt : post.title}
                        className={styles.image}
                        loading="lazy"
                        {...getImageDimensions(post.image)}
                      />
                      <span className={styles.categoryBadge}>
                        {('subcategory' in post && post.subcategory) ? post.subcategory : post.category}
                      </span>
                    </div>
                  </Link>
                )}
                <div className={styles.content}>
                  <div className={styles.meta}>
                    <time dateTime={post.date}>
                      {new Date(post.date).toLocaleDateString('he-IL', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                      })}
                    </time>
                  </div>

                  <h2 className={styles.cardTitle}>
                    <Link to={`/blog/${post.id}`} className={styles.titleLink}>
                      {post.title}
                    </Link>
                  </h2>

                  <p className={styles.excerpt}>{post.excerpt}</p>

                  <div className={styles.cardFooter}>
                    <Link to={`/blog/${post.id}`} className={styles.readMore} aria-label={`קרא עוד על ${post.title}`}>
                      קרא עוד ←
                    </Link>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>🔍</div>
            <h3>לא נמצאו מאמרים תואמים</h3>
            <p>נסה לחפש מילים אחרות או לאפס את הניווט והסינונים.</p>
            <button
              type="button"
              className={styles.emptyButton}
              onClick={() => {
                setSelectedCategory('הכל');
                setSearchQuery('');
              }}
            >
              הצג את כל המאמרים
            </button>
          </div>
        )}
      </main>
    </div>
  );
};

export default BlogList;
