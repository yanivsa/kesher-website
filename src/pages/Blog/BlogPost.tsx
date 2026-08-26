import React, { useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import DOMPurify from 'dompurify';
import posts from '../../data/publishedPosts';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import LeadMagnet from '../../components/LeadMagnet/LeadMagnet';
import ShareButtons from '../../components/ShareButtons/ShareButtons';
import { SITE_CONFIG } from '../../constants/siteConfig';
import { getImageDimensions } from '../../data/imageDimensions';
import NotFound from '../NotFound/NotFound';
import articleVideoMap from '../../data/articleVideos.json';
import styles from './BlogPost.module.css';

type ArticleVideo = { youtubeId: string; title: string };
const articleVideos = articleVideoMap as Record<string, ArticleVideo>;

const BlogPost: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const post = posts.find(p => p.id === id);
  const [videoActive, setVideoActive] = useState(false);

  const schemaData = useMemo(() => ({
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Article",
        "headline": post?.title || "",
        ...(post?.image ? { "image": `${SITE_CONFIG.url}${post.image}` } : {}),
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
  }), [post]);

  if (!post) {
    return <NotFound />;
  }

  const safeContent = DOMPurify.sanitize(post.content);
  const shareUrl = `${SITE_CONFIG.url}/blog/${post.id}`;
  const articleVideo = articleVideos[post.id];
  const relatedService = 'serviceUrl' in post
    && 'serviceLabel' in post
    && typeof post.serviceUrl === 'string'
    && typeof post.serviceLabel === 'string'
    ? { url: post.serviceUrl, label: post.serviceLabel }
    : null;

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
          <ShareButtons
            title={post.title}
            url={shareUrl}
            itemId={post.id}
            placement="article_top"
          />
        </div>
      </header>
      <div className={`container ${styles.container}`}>
        <div className={styles.mainContent}>
          {post.image && (
            <div className={styles.imageWrapper}>
              <img
                src={post.image}
                alt={post.imageAlt || post.title}
                className={styles.image}
                fetchPriority="high"
                {...getImageDimensions(post.image)}
              />
            </div>
          )}
          {articleVideo && (
            <section className={styles.articleVideoCard} aria-label="וידאו נלווה למאמר">
              <div className={styles.articleVideoHeader}>
                <span className={styles.articleVideoEyebrow}>גם בווידאו</span>
                <h2>{articleVideo.title}</h2>
                <p>מעדיפים לצפות? הסרטון מסכם ומרחיב את הנקודות המרכזיות במאמר.</p>
              </div>
              <div className={styles.articleVideoFrame}>
                {videoActive ? (
                  <iframe
                    src={`https://www.youtube-nocookie.com/embed/${articleVideo.youtubeId}?autoplay=1&rel=0`}
                    title={articleVideo.title}
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    allowFullScreen
                    loading="lazy"
                  />
                ) : (
                  <button
                    type="button"
                    className={styles.articleVideoFacade}
                    onClick={() => setVideoActive(true)}
                    aria-label={`נגן את הסרטון: ${articleVideo.title}`}
                  >
                    {post.image && <img src={post.image} alt="" loading="lazy" aria-hidden="true" />}
                    <span className={styles.articleVideoShade} />
                    <span className={styles.articleVideoPlay} aria-hidden="true">▶</span>
                  </button>
                )}
              </div>
              <a
                className={styles.articleVideoLink}
                href={`https://www.youtube.com/watch?v=${articleVideo.youtubeId}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                צפייה ישירה ב-YouTube ↗
              </a>
            </section>
          )}
          <div className={styles.content} dangerouslySetInnerHTML={{ __html: safeContent }} />
          <ShareButtons
            title={post.title}
            url={shareUrl}
            itemId={post.id}
            placement="article_bottom"
          />
          <p className={styles.disclaimer}>המאמר מספק מידע כללי ואינו מחליף ייעוץ מקצועי המותאם למצב האישי או המשפחתי.</p>
          <LeadMagnet />
        </div>
        <aside className={styles.sidebar}>
          {'video' in post && post.video && (
            <div className={styles.videoCard}>
              <h3>🎬 הסבר קצר בנושא</h3>
              <div className={styles.videoWrapper}>
                <video
                  src={post.video as string}
                  controls
                  playsInline
                  preload="metadata"
                  className={styles.video}
                  poster={post.image || undefined}
                />
              </div>
            </div>
          )}
          <div className={styles.ctaCard}>
            <h3>צריכים עזרה עם הנושא הזה?</h3>
            <p>אני כאן כדי ללוות אתכם בתהליך אישי ומותאם לכם.</p>
            {relatedService && (
              <Link to={relatedService.url} className={styles.ctaButton}>{relatedService.label}</Link>
            )}
            <Link to={SITE_CONFIG.links.appointment} className={styles.ctaButton}>קביעת פגישת ייעוץ</Link>
          </div>
        </aside>
      </div>
    </article>
  );
};

export default BlogPost;
