import React from 'react';
import Hero from './Hero';
import ServicesSection from './ServicesSection';
import AboutSection from './AboutSection';
import BlogPreview from './BlogPreview';
import ContactSection from './ContactSection';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import styles from './Home.module.css';

const Home: React.FC = () => {
  const schemaData = {
    "@context": "https://schema.org",
    "@type": "Therapist",
    "name": "שירה שחרוני — ייעוץ זוגי, הדרכת הורים וגישור",
    "url": "https://shira.saharoni.com",
    "telephone": "+972-50-000-0000",
    "address": {
      "@type": "PostalAddress",
      "addressLocality": "אשדוד",
      "addressCountry": "IL"
    },
    "serviceType": ["ייעוץ זוגי", "הדרכת הורים", "גישור גירושין"],
    "description": "יועצת זוגית ומגשרת מוסמכת באשדוד עם ניסיון בהדרכת הורים לילדים עם ADHD"
  };

  return (
    <div className={styles.home}>
      <MetaTags 
        title="שירה שחרוני — ייעוץ זוגי, הדרכת הורים וגישור באשדוד"
        description="יועצת זוגית ומנחת הורים מוסמכת באשדוד. ייעוץ זוגי, הדרכת הורים וגישור גירושין. קבעו שיחת היכרות ▸"
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
