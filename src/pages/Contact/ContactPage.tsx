import React from 'react';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import ContactSection from '../Home/ContactSection';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './ContactPage.module.css';

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "ContactPage",
      "name": "צור קשר | שירה סהרוני",
      "description": "צרו קשר עם שירה סהרוני לתיאום פגישת ייעוץ זוגי, הדרכת הורים או גישור. זמינה באשדוד וב-Zoom.",
      "url": `${SITE_CONFIG.url}/contact`,
      "mainEntity": {
        "@type": "LocalBusiness",
        "name": SITE_CONFIG.brand,
        "telephone": SITE_CONFIG.contact.phone,
        "email": SITE_CONFIG.contact.email,
        "address": {
          "@type": "PostalAddress",
          "addressLocality": "אשדוד",
          "addressCountry": "IL"
        }
      }
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
          "name": "צור קשר",
          "item": `${SITE_CONFIG.url}/contact`
        }
      ]
    }
  ]
};

const ContactPage: React.FC = () => {

  return (
    <div className={styles.page}>
      <SchemaOrg data={schemaData} />
      <MetaTags 
        title="צור קשר | שירה סהרוני" 
        description="צרו קשר עם שירה סהרוני לתיאום פגישת ייעוץ זוגי, הדרכת הורים או גישור. זמינה באשדוד וב-Zoom." 
      />
      <header className={styles.header}>
        <div className="container">
          <h1>צרו קשר</h1>
          <p>צעד ראשון לקראת שינוי מתחיל בשיחה אחת.</p>
        </div>
      </header>
      <ContactSection />
    </div>
  );
};

export default ContactPage;
