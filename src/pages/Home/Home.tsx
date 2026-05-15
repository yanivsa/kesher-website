import React from 'react';
import Hero from './Hero';
import ServicesSection from './ServicesSection';
import AboutSection from './AboutSection';
import BlogPreview from './BlogPreview';
import ContactSection from './ContactSection';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './Home.module.css';

const Home: React.FC = () => {
  const schemaData = {
    "@context": "https://schema.org",
    "@type": "Therapist",
    "name": `${SITE_CONFIG.author} — ייעוץ זוגי, הדרכת הורים וגישור`,
    "url": "https://shira.saharoni.com",
    "telephone": SITE_CONFIG.contact.phone,
    "address": {
      "@type": "PostalAddress",
      "addressLocality": "אשדוד",
      "addressCountry": "IL"
    },
    "serviceType": ["ייעוץ זוגי", "הדרכת הורים", "גישור גירושין"],
    "description": SITE_CONFIG.description
  };

  return (
    <div className={styles.home}>
      <MetaTags 
        title={`${SITE_CONFIG.author} — ייעוץ זוגי, הדרכת הורים וגישור באשדוד`}
        description={SITE_CONFIG.description}
      />
      <SchemaOrg data={schemaData} />
      <Hero />
      <ServicesSection />
      <AboutSection />
      <BlogPreview />
      <ContactSection />
    </div>
  );
};

export default Home;
