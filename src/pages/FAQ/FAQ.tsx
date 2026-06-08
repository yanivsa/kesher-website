import React, { useState } from 'react';
import { FiChevronDown } from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import faqs from '../../data/faqs';
import styles from './FAQ.module.css';

const categories = ['הכל', 'ייעוץ זוגי', 'הדרכת הורים', 'כללי'];

// FAQPage Schema for SEO/GEO
const faqSchema = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "FAQPage",
      "mainEntity": faqs.map(faq => ({
        "@type": "Question",
        "name": faq.question,
        "acceptedAnswer": {
          "@type": "Answer",
          "text": faq.answer
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
          "name": "שאלות נפוצות",
          "item": `${SITE_CONFIG.url}/faq`
        }
      ]
    }
  ]
};

const FAQ: React.FC = () => {
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  const [activeCategory, setActiveCategory] = useState('הכל');

  const filteredFaqs = activeCategory === 'הכל' 
    ? faqs 
    : faqs.filter(f => f.category === activeCategory);

  const toggle = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };


  return (
    <div className={styles.faq}>
      <MetaTags 
        title="שאלות נפוצות | שירה סהרוני — ייעוץ זוגי והנחיית הורים" 
        description="תשובות על הכנה לחתונה לזוגות שרוצים להתחיל נכון, מתחתנים עם הורים גרושים או ADHD, הכנה לכיתה א', ייעוץ זוגי והדרכת הורים."
      />
      <SchemaOrg data={faqSchema} />
      <header className={styles.header}>
        <div className="container">
          <h1>שאלות נפוצות</h1>
          <p>תשובות לשאלות שמעסיקות זוגות, הורים ומשפחות בתהליכי שינוי.</p>
        </div>
      </header>
      <div className={`container ${styles.container}`}>
        <div className={styles.categories}>
          {categories.map(cat => (
            <button 
              type="button"
              key={cat}
              className={`${styles.categoryBtn} ${activeCategory === cat ? styles.active : ''}`}
              onClick={() => { setActiveCategory(cat); setOpenIndex(null); }}
            >
              {cat}
            </button>
          ))}
        </div>
        <div className={styles.list}>
          {filteredFaqs.map((faq, index) => (
            <div 
              key={`${activeCategory}-${index}`} 
              className={`${styles.item} ${openIndex === index ? styles.open : ''}`}
            >
              <button 
                type="button"
                className={styles.question} 
                onClick={() => toggle(index)}
                aria-expanded={openIndex === index}
              >
                <span>{faq.question}</span>
                <FiChevronDown className={styles.chevron} />
              </button>
              <div className={styles.answerWrapper}>
                <p className={styles.answer}>{faq.answer}</p>
              </div>
            </div>
          ))}
        </div>

        <div className={styles.cta}>
          <h3>לא מצאתם תשובה?</h3>
          <p>אני כאן לכל שאלה. שלחו הודעה ואחזור אליכם תוך 24 שעות.</p>
          <a href="https://wa.me/972502763802" className={styles.ctaBtn}>
            שאלו אותי בוואטסאפ
          </a>
        </div>
      </div>
    </div>
  );
};

export default FAQ;
