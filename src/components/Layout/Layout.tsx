import React from 'react';
import Header from './Header';
import Footer from './Footer';
import FloatingWhatsApp from './FloatingWhatsApp';
import GeoBanner from '../GEO/GeoBanner';
import styles from './Layout.module.css';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  return (
    <div className={styles.wrapper}>
      <GeoBanner />
      <Header />
      <main className={styles.main}>
        {children}
      </main>
      <Footer />
      <FloatingWhatsApp />
    </div>
  );
};

export default Layout;
