import React from 'react';
import { useLocation } from 'react-router-dom';
import Header from './Header';
import Footer from './Footer';
import FloatingWhatsApp from './FloatingWhatsApp';
import GeoBanner from '../GEO/GeoBanner';
import MobileStickyBar from './MobileStickyBar';
import AIChatbot from '../AIChatbot/AIChatbot';
import SiteAttributionTracker from '../Analytics/SiteAttributionTracker';
import styles from './Layout.module.css';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { pathname } = useLocation();
  const cleanPath = pathname.replace(/\/$/, '');
  const usesStandaloneHomepage = cleanPath === ''
    || cleanPath === '/beta'
    || cleanPath === '/beta3'
    || cleanPath === '/b'
    || cleanPath === '/couples-counseling-ashdod'
    || cleanPath === '/thank-you-booked'
    || cleanPath === '/thank-you-contact';

  if (usesStandaloneHomepage) {
    return (
      <div className={styles.wrapper}>
        <SiteAttributionTracker />
        <a className="skip-link" href="#main-content">דילוג לתוכן הראשי</a>
        {children}
      </div>
    );
  }

  return (
    <div className={styles.wrapper}>
      <SiteAttributionTracker />
      <a className="skip-link" href="#main-content">דילוג לתוכן הראשי</a>
      <GeoBanner />
      <Header />
      <main id="main-content" className={styles.main}>
        {children}
      </main>
      <Footer />
      <FloatingWhatsApp />
      <MobileStickyBar />
      <AIChatbot />
    </div>
  );
};

export default Layout;
