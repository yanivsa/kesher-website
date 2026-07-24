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
        "גישור",
        "ילדים מחוננים",
        "הכנה למסגרת מחוננים",
        "משפחות עולים",
        "תושבים חוזרים",
        "ADHD",
        "תקשורת בזוגיות",
        "הורות משותפת"
      ],
      "makesOffer": [
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "ייעוץ זוגי",
            "url": `${SITE_CONFIG.url}/services/couples`,
            "description": "ייעוץ זוגי לשיפור תקשורת, התמודדות עם משברים וחיזוק הקשר."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "הדרכת הורים",
            "url": `${SITE_CONFIG.url}/services/parenting`,
            "description": "הדרכה להורים לילדים מחוננים ולילדים עם ADHD, כולל מעברים חינוכיים ותפקודים ניהוליים."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "גישור",
            "url": `${SITE_CONFIG.url}/services/mediation`,
            "description": "גישור לבני זוג, משפחות, הורים, שכנים ושותפים לצורך בניית הסכמות מעשיות."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "הנחיית הורים לילדים מחוננים",
            "url": `${SITE_CONFIG.url}/services/gifted-parenting`,
            "description": "ליווי סביב רגישות, פרפקציוניזם, שייכות והכנה רגשית וניהולית למסגרת מחוננים."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "משפחות עולים ותושבים חוזרים",
            "url": `${SITE_CONFIG.url}/services/aliyah-families`,
            "description": "ייעוץ זוגי והנחיית הורים בתקופת עלייה או חזרה לישראל, כולל הסתגלות ובניית תחושת בית."
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
        title={`${SITE_CONFIG.author} — ייעוץ זוגי, הנחיית הורים וגישור באשדוד`}
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
