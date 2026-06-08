import React, { useMemo } from 'react';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import AboutSection from '../Home/AboutSection';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './AboutPage.module.css';

const AboutPage: React.FC = () => {

  const schemaData = useMemo(() => {
    const currentDate = new Date().toISOString().split('T')[0];
    return {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "ProfilePage",
          "dateCreated": "2024-01-01",
          "dateModified": currentDate,
          "mainEntity": {
            "@type": "Person",
            "name": SITE_CONFIG.author,
            "alternateName": "Shira Saharoni",
            "jobTitle": ["יועצת זוגית", "מנחת הורים"],
            "description": "הכירו את שירה סהרוני - יועצת זוגית ומנחת הורים באשדוד. שילוב ייחודי של כלים טיפוליים וראייה מערכתית רגישה.",
            "url": `${SITE_CONFIG.url}/about`,
            "image": `${SITE_CONFIG.url}/images/generated/site/about-office.png`,
            "worksFor": {
              "@type": "LocalBusiness",
              "name": SITE_CONFIG.brand
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
              "name": "אודות",
              "item": `${SITE_CONFIG.url}/about`
            }
          ]
        }
      ]
    };
  }, []);

  return (
    <div className={styles.page}>
      <SchemaOrg data={schemaData} />
      <MetaTags 
        title="אודות שירה סהרוני | יועצת זוגית ומנחת הורים באשדוד" 
        description="הכירו את שירה סהרוני - יועצת זוגית ומנחת הורים באשדוד. שילוב ייחודי של כלים טיפוליים וראייה מערכתית רגישה." 
      />
      <header className={styles.header}>
        <div className="container">
          <h1>אודותי</h1>
          <p>ליווי רגיש ומקצועי למען מערכות היחסים שלכם.</p>
        </div>
      </header>
      <AboutSection />
      <section className={styles.extraContent}>
        <div className="container">
          <h2>האני המאמין שלי</h2>
          <p>
            אני מאמינה שכל אדם וכל זוג נושאים בתוכם את הכוח לשינוי. התפקיד שלי הוא להעניק את המרחב הבטוח, את הכלים המקצועיים ואת הליווי הרגיש שמאפשר לכוח הזה לצאת אל הפועל.
          </p>
          <p>
            בין אם זה בהדרכת הורים או בספת הייעוץ הזוגי, המטרה שלי היא תמיד אחת: לייצר חיבור. חיבור של אדם לעצמו, חיבור בין בני זוג, וחיבור בין הורים לילדיהם.
          </p>
        </div>
      </section>
    </div>
  );
};

export default AboutPage;
