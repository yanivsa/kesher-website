import React from 'react';
import MetaTags from '../SEO/MetaTags';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './ServicePageTemplate.module.css';

interface ServicePageTemplateProps {
  title: string;
  description: string;
  heroTitle: string;
  heroSubtitle: string;
  content: React.ReactNode;
  icon: string;
  image: string;
}

const ServicePageTemplate: React.FC<ServicePageTemplateProps> = ({ 
  title, 
  description, 
  heroTitle, 
  heroSubtitle, 
  content,
  icon,
  image
}) => {
  return (
    <div className={styles.page}>
      <MetaTags title={title} description={description} />
      <header className={styles.hero}>
        <div className={`container ${styles.heroContainer}`}>
          <div className={styles.heroContent}>
            <div className={styles.icon}>{icon}</div>
            <h1>{heroTitle}</h1>
            <p className={styles.subtitle}>{heroSubtitle}</p>
          </div>
          <div className={styles.heroImageWrapper}>
            <img src={image} alt={heroTitle} className={styles.heroImage} fetchPriority="high" />
          </div>
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
          <a href={SITE_CONFIG.links.appointment} className={styles.ctaButton}>קביעת פגישת ייעוץ</a>
        </div>
      </section>
    </div>
  );
};

export default ServicePageTemplate;
