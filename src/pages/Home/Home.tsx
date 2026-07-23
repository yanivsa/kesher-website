import React from 'react';
import Hero from './Hero';
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
      "areaServed": [
        {
          "@type": "City",
          "name": "אשדוד"
        },
        {
          "@type": "Country",
          "name": "ישראל"
        }
      ],
      "availableLanguage": "he",
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
            "description": "הנחיית הורים סביב מחוננות, רגישות, שייכות, תפקודים ניהוליים והכנה למסגרת מחוננים."
          }
        },
        {
          "@type": "Offer",
          "itemOffered": {
            "@type": "Service",
            "name": "ליווי משפחות עולים ותושבים חוזרים",
            "url": `${SITE_CONFIG.url}/services/aliyah-families`,
            "description": "ייעוץ זוגי והנחיית הורים למשפחות בתקופת עלייה לישראל או חזרה אליה."
          }
        }
      ],
      "image": `${SITE_CONFIG.url}/images/generated/site/home-hero.jpg`,
      "priceRange": "$$",
      "potentialAction": {
        "@type": "ReserveAction",
        "target": {
          "@type": "EntryPoint",
          "urlTemplate": `${SITE_CONFIG.url}/appointment`,
          "inLanguage": "he"
        }
      }
    },
    {
      "@type": "Person",
      "@id": `${SITE_CONFIG.url}/#shira`,
      "name": SITE_CONFIG.author,
      "alternateName": "Shira Saharoni",
      "url": `${SITE_CONFIG.url}/about`,
      "jobTitle": [
        "יועצת זוגית",
        "מנחת הורים",
        "מגשרת מוסמכת"
      ],
      "worksFor": {
        "@id": `${SITE_CONFIG.url}/#business`
      },
      "knowsAbout": [
        "ייעוץ זוגי",
        "הנחיית הורים",
        "גישור",
        "ילדים מחוננים",
        "תפקודים ניהוליים",
        "משפחות עולים ותושבים חוזרים"
      ]
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
      <ServicesSection />
      <AboutSection />
      <ProcessSection />
      <WhyMeSection />
      <Testimonials />
      <BlogPreview />
      <div className="container">
        <LeadMagnet />
      </div>
      <ContactSection />
    </div>
  );
};

export default Home;
