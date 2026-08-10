import React, { useState, useMemo } from 'react';
import { FiChevronDown } from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import faqs from '../../data/faqs';
import styles from './FAQ.module.css';

const categories = ['הכל', 'ייעוץ זוגי', 'הכנה לנישואים והשנה הראשונה', 'זוגיות בעלייה ורילוקיישן', 'רווקות מאוחרת', 'מציאת זוגיות', 'הדרכת הורים', 'תחומי התמחות', 'כללי'];

// FAQPage Schema for SEO/GEO
const faqSchema = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "FAQPage",
      "url": `${SITE_CONFIG.url}/faq`,
      "description": "תשובות על ייעוץ זוגי, הכנה לנישואים, השנה הראשונה, זוגיות בעלייה וברילוקיישן, רווקות מאוחרת, הנחיית הורים.",
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

  const filteredFaqs = useMemo(() => {
    return activeCategory === 'הכל'
      ? faqs
      : faqs.filter(f => f.category === activeCategory);
  }, [activeCategory]);

  const toggle = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };


  return (
    <div className={styles.faq}>
      <MetaTags 
        title="שאלות נפוצות | ייעוץ והנחיית הורים"
        description="תשובות על ייעוץ זוגי, הכנה לנישואים, השנה הראשונה, זוגיות בעלייה וברילוקיישן, רווקות מאוחרת, הנחיית הורים."
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
          <p>נשארה שאלה? אפשר לשלוח לי הודעה ואחזור אליכם בהקדם.</p>
          <a href="https://wa.me/972502763802" className={styles.ctaBtn}>
            שאלו אותי בוואטסאפ
          </a>
        </div>
      </div>
    </div>
  );
};

export default FAQ;
