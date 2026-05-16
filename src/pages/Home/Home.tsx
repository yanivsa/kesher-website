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
    "@graph": [
      {
        "@type": "Therapist",
        "@id": "https://shira.saharoni.com/#therapist",
        "name": SITE_CONFIG.author,
        "alternateName": "Shira Saharoni",
        "url": "https://shira.saharoni.com",
        "telephone": SITE_CONFIG.contact.phone,
        "description": SITE_CONFIG.description,
        "address": {
          "@type": "PostalAddress",
          "addressLocality": "אשדוד",
          "addressCountry": "IL"
        },
        "knowsAbout": [
          "ייעוץ זוגי",
          "הדרכת הורים",
          "גישור גירושין",
          "ADHD",
          "תקשורת בזוגיות",
          "הורות משותפת"
        ],
        "hasCredential": [
          {
            "@type": "EducationalOccupationalCredential",
            "credentialCategory": "עורכת דין"
          },
          {
            "@type": "EducationalOccupationalCredential",
            "credentialCategory": "מגשרת מוסמכת"
          }
        ]
      },
      {
        "@type": "LocalBusiness",
        "name": SITE_CONFIG.brand,
        "image": "https://images.unsplash.com/photo-1521791136064-7986c2920216?auto=format&fit=crop&w=1200&q=80",
        "address": {
          "@type": "PostalAddress",
          "addressLocality": "אשדוד",
          "addressCountry": "IL"
        },
        "telephone": SITE_CONFIG.contact.phone,
        "priceRange": "$$"
      }
    ]
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
