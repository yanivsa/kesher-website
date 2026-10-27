import React from 'react';
import { Link, useParams } from 'react-router-dom';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import faqs from '../../data/faqs';
import NotFound from '../NotFound/NotFound';
import styles from './FAQ.module.css';

const FaqDetail: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const faq = faqs.find((item) => item.slug === slug);

  if (!faq) return <NotFound />;

  const url = `${SITE_CONFIG.url}/faq/${faq.slug}`;
  const paragraphs = faq.longAnswer && faq.longAnswer.length > 0 ? faq.longAnswer : [faq.answer];
  const others = faqs.filter((item) => item.slug && item.slug !== faq.slug).slice(0, 5);

  const schema = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "FAQPage",
        "@id": `${url}#faq`,
        "url": url,
        "mainEntity": [{
          "@type": "Question",
          "name": faq.question,
          "acceptedAnswer": { "@type": "Answer", "text": paragraphs.join(' ') }
        }]
      },
      {
        "@type": "BreadcrumbList",
        "@id": `${url}#breadcrumb`,
        "itemListElement": [
          { "@type": "ListItem", "position": 1, "name": "עמוד הבית", "item": SITE_CONFIG.url },
          { "@type": "ListItem", "position": 2, "name": "שאלות נפוצות", "item": `${SITE_CONFIG.url}/faq` },
          { "@type": "ListItem", "position": 3, "name": faq.question, "item": url }
        ]
      }
    ]
  };

  return (
    <div className={styles.faq}>
      <MetaTags
        title={`${faq.question} | שירה סהרוני`}
        description={faq.answer}
        canonical={url}
      />
      <SchemaOrg data={schema} />
      <header className={styles.header}>
        <div className="container">
          <p className={styles.breadcrumb}>
            <Link to="/faq">שאלות נפוצות</Link>
            <span aria-hidden="true"> / </span>
            <span>{faq.category}</span>
          </p>
          <h1>{faq.question}</h1>
        </div>
      </header>
      <div className={`container ${styles.container}`}>
        <div className={styles.detailBody}>
          {paragraphs.map((paragraph, index) => (
            <p key={index} className={styles.detailParagraph}>{paragraph}</p>
          ))}
        </div>

        {faq.related && (
          <div className={styles.relatedBox}>
            <h2>רוצים להמשיך מכאן?</h2>
            <p>אם השאלה הזו מעסיקה אתכם, אפשר לקרוא עוד על הליווי שמתאים לנושא, או פשוט לקבוע פגישה ראשונה.</p>
            <Link className={styles.ctaBtn} to={faq.related.href}>{faq.related.label}</Link>
          </div>
        )}

        <div className={styles.moreQuestions}>
          <h2>שאלות נוספות שאנשים שואלים</h2>
          <ul>
            {others.map((item) => (
              <li key={item.slug}>
                <Link to={`/faq/${item.slug}`}>{item.question}</Link>
              </li>
            ))}
          </ul>
          <Link className={styles.moreLink} to="/faq">לכל השאלות הנפוצות ←</Link>
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

export default FaqDetail;
