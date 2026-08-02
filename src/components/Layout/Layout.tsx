import React from 'react';
import { useLocation } from 'react-router-dom';
import Header from './Header';
import Footer from './Footer';
import FloatingWhatsApp from './FloatingWhatsApp';
import GeoBanner from '../GEO/GeoBanner';
import MobileStickyBar from './MobileStickyBar';
import AIChatbot from '../AIChatbot/AIChatbot';
import styles from './Layout.module.css';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { pathname } = useLocation();
  const cleanPath = pathname.length > 1 && pathname.endsWith('/') ? pathname.slice(0, -1) : pathname;
  const usesStandalonePage = cleanPath === '/'
    || cleanPath === '/b'
    || cleanPath === '/beta'
    || cleanPath === '/couples-counseling-ashdod';

  if (usesStandalonePage) {
    return (
      <div className={styles.wrapper}>
        <a className="skip-link" href="#main-content">דילוג לתוכן הראשי</a>
        {children}
      </div>
    );
  }

  return (
    <div className={styles.wrapper}>
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
