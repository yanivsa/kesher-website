import React from 'react';
import MetaTags from '../SEO/MetaTags';
import SchemaOrg from '../SEO/SchemaOrg';
import styles from './ServicePageTemplate.module.css';

interface ServicePageTemplateProps {
  title: string;
  description: string;
  heroTitle: string;
  heroSubtitle: string;
  content: React.ReactNode;
  icon: string;
}

const ServicePageTemplate: React.FC<ServicePageTemplateProps> = ({ 
  title, 
  description, 
  heroTitle, 
  heroSubtitle, 
  content,
  icon
}) => {
  return (
    <div className={styles.page}>
      <MetaTags title={title} description={description} />
      <header className={styles.hero}>
        <div className="container">
          <div className={styles.icon}>{icon}</div>
          <h1>{heroTitle}</h1>
          <p className={styles.subtitle}>{heroSubtitle}</p>
        </div>
      </header>
      <section className={styles.contentSection}>
        <div className="container">
          {content}
        </div>
      </section>
      <section className={styles.ctaSection}>
        <div className="container">
          <h2>מוכנים להתחיל בשינוי?</h2>
          <p>אני כאן כדי ללוות אתכם בתהליך.</p>
          <a href="/#contact" className={styles.ctaButton}>לקביעת פגישת היכרות</a>
        </div>
      </section>
    </div>
  );
};

export default ServicePageTemplate;
