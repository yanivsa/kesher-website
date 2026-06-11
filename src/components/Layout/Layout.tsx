import React, { lazy, Suspense } from 'react';
import Header from './Header';
import Footer from './Footer';
import FloatingWhatsApp from './FloatingWhatsApp';
import GeoBanner from '../GEO/GeoBanner';
import MobileStickyBar from './MobileStickyBar';
import styles from './Layout.module.css';

const AIChatbot = lazy(() => import('../AIChatbot/AIChatbot'));

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
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
      <Suspense fallback={null}><AIChatbot /></Suspense>
    </div>
  );
};

export default Layout;
