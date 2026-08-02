import React, { useEffect } from 'react';
import { FiCheckCircle, FiHome, FiMessageCircle } from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './ThankYouPage.module.css';

const ThankYouContactPage: React.FC = () => {
  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({
        event: 'thank_you_view',
        page_type: 'thank_you_contact',
        service_type: 'couples_counseling',
        service_region: 'ashdod',
        timestamp: new Date().toISOString(),
      });
    }
  }, []);

  const whatsappMessage = encodeURIComponent(
    'שלום שירה, פניתי דרך טופס היצירת קשר באתר.',
  );
  const whatsappUrl = `https://wa.me/${SITE_CONFIG.contact.whatsapp}?text=${whatsappMessage}`;

  return (
    <div className={styles.page}>
      <MetaTags
        title="הפנייה התקבלה | שירה סהרוני"
        description="אישור קבלת פנייה."
        canonical={`${SITE_CONFIG.url}/thank-you-contact`}
        noindex={true}
      />

      <header className={styles.header}>
        <div className={`container ${styles.headerInner}`}>
          <a href="/" className={styles.brand} aria-label="לדף הבית של שירה סהרוני">
            <span className={styles.brandTitle}>שירה סהרוני</span>
            <span className={styles.brandSubtitle}>קשר | ייעוץ זוגי</span>
          </a>
        </div>
      </header>

      <main className={styles.mainContent}>
        <div className={styles.card}>
          <div className={styles.iconWrapper}>
            <FiCheckCircle aria-hidden="true" />
          </div>
          <h1>הפנייה התקבלה</h1>
          <p>
            תודה שפנית. הפנייה התקבלה בהצלחה ותענה בהקדם המהיר ביותר.
          </p>

          <div className={styles.actions}>
            <a href="/" className={styles.btnPrimary}>
              <FiHome aria-hidden="true" />
              חזרה לדף הבית
            </a>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.btnSecondary}
            >
              <FiMessageCircle aria-hidden="true" />
              פנייה ישירה ב-WhatsApp
            </a>
          </div>
        </div>
      </main>

      <footer className={styles.footer}>
        <div className="container">
          © {new Date().getFullYear()} שירה סהרוני. כל הזכויות שמורות.
        </div>
      </footer>
    </div>
  );
};

export default ThankYouContactPage;
