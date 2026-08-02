import React, { useEffect } from 'react';
import { FiCheckCircle, FiHome, FiMessageCircle } from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './ThankYouPage.module.css';

const ThankYouBookedPage: React.FC = () => {
  useEffect(() => {
    // Push thank_you_view event to dataLayer safely (does NOT push duplicate booking_confirmed)
    if (typeof window !== 'undefined') {
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({
        event: 'thank_you_view',
        page_type: 'thank_you_booked',
        service_type: 'couples_counseling',
        service_region: 'ashdod',
        timestamp: new Date().toISOString(),
      });
    }
  }, []);

  const whatsappMessage = encodeURIComponent(
    'שלום שירה, נקבעה פגישה דרך האתר ויש לי שאלה.',
  );
  const whatsappUrl = `https://wa.me/${SITE_CONFIG.contact.whatsapp}?text=${whatsappMessage}`;

  return (
    <div className={styles.page}>
      <MetaTags
        title="הפגישה נקבעה | שירה סהרוני"
        description="אישור קביעת פגישת ייעוץ זוגי."
        canonical={`${SITE_CONFIG.url}/thank-you-booked`}
        noIndex={true}
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
          <h1>הפגישה נקבעה</h1>
          <p>
            פרטי הפגישה נשלחו בהתאם לפרטים שהוזנו ביומן. ניתן לשנות או לבטל את המועד באמצעות הקישור שבהודעת האישור.
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
              יש לכם שאלה? כתבו ב-WhatsApp
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

export default ThankYouBookedPage;
