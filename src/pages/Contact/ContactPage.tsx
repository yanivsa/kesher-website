import React from 'react';
import MetaTags from '../../components/SEO/MetaTags';
import ContactSection from '../Home/ContactSection';
import styles from './ContactPage.module.css';

const ContactPage: React.FC = () => {
  return (
    <div className={styles.page}>
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
