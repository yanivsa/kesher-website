import React from 'react';
import styles from './BlogPreview.module.css';

const BlogPreview: React.FC = () => {
  const posts = [
    {
      title: 'התפטרות שקטה בסלון: כשהזוגיות הופכת ללוגיסטיקה',
      excerpt: 'איך לזהות את הרגע שבו הפסקנו לדבר על הרגשות שלנו והתחלנו לדבר רק על מי מוציא את הילד מהגן.',
      image: '📚',
      link: '#blog/quiet-resignation'
    },
    {
      title: 'חמש דקות של חסד: הטיפ הקטן שמשנה תקשורת זוגית',
      excerpt: 'לפעמים כל מה שצריך זה חמש דקות של הקשבה נקייה בכל יום כדי למנוע את הפיצוץ הבא.',
      image: '⏱️',
      link: '#blog/5-minutes'
    },
    {
      title: 'הורות לילדי ADHD: לא מה שחשבתם',
      excerpt: 'איך להפוך את האתגר של הפרעת הקשב למנוע של יצירתיות וחיבור משפחתי עמוק.',
      image: '🧠',
      link: '#blog/adhd-parenting'
    }
  ];

  return (
    <section id="blog" className={styles.blog}>
      <div className="container">
        <div className={styles.header}>
          <h2 className={styles.title}>מהבלוג שלי</h2>
          <a href="#blog" className={styles.viewAll}>לכל המאמרים ←</a>
        </div>
        <div className={styles.grid}>
          {posts.map((post, index) => (
            <article key={index} className={styles.card}>
              <div className={styles.imagePlaceholder}>{post.image}</div>
              <div className={styles.content}>
                <h3 className={styles.postTitle}>{post.title}</h3>
                <p className={styles.excerpt}>{post.excerpt}</p>
                <a href={post.link} className={styles.readMore}>קרא עוד</a>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
};

export default BlogPreview;
