import React from 'react';
import Hero from './Hero';
import TrustSection from './TrustSection';
import ServicesSection from './ServicesSection';
import ProcessSection from './ProcessSection';
import WhyMeSection from './WhyMeSection';
import Testimonials from './Testimonials';
import AboutSection from './AboutSection';
import BlogPreview from './BlogPreview';
import LeadMagnet from '../../components/LeadMagnet/LeadMagnet';
import ContactSection from './ContactSection';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './Home.module.css';

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "LocalBusiness",
      "@id": `${SITE_CONFIG.url}/#business`,
      "name": SITE_CONFIG.author,
      "alternateName": "Shira Saharoni",
      "url": SITE_CONFIG.url,
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
        "ADHD",
        "תקשורת בזוגיות",
        "הורות משותפת"
      ],
      "hasCredential": [
        {
          "@type": "EducationalOccupationalCredential",
          "credentialCategory": "יועצת זוגית ומשפחתית"
        }
      ],
      "serviceType": ["ייעוץ זוגי", "הדרכת הורים", "טיפול מקוון"],
      "makesOffer": [
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "ייעוץ זוגי",
            "description": "טיפול זוגי לשיפור תקשורת, התמודדות עם משברים, בגידות ואינטימיות. גישות Gottman ו-EFT."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "הדרכת הורים",
            "description": "הדרכה מקצועית להורים לילדים עם ADHD, הצבת גבולות, והורות משותפת לאחר פרידה."
          }
        }
      ],
      "image": `${SITE_CONFIG.url}/images/generated/site/home-hero.jpg`,
      "priceRange": "$$"
    }
  ]
};

const Home: React.FC = () => {

  return (
    <div className={styles.home}>
      <MetaTags 
        title={`${SITE_CONFIG.author} — ייעוץ זוגי והדרכת הורים באשדוד`}
        description={SITE_CONFIG.description}
      />
      <SchemaOrg data={schemaData} />
      <Hero />
      <TrustSection />
      <ServicesSection />
      <ProcessSection />
      <WhyMeSection />
      <Testimonials />
      <AboutSection />
      <BlogPreview />
      <div className="container">
        <LeadMagnet />
      </div>
      <ContactSection />
    </div>
  );
};

export default Home;
