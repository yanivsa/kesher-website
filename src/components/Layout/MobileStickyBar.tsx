import React, { useEffect, useState } from 'react';
import { FaWhatsapp, FaPhoneAlt } from 'react-icons/fa';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './MobileStickyBar.module.css';

const MobileStickyBar: React.FC = () => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      // Show after scrolling down a bit so it doesn't clutter the initial hero view
      if (window.scrollY > 300) {
        setIsVisible(true);
      } else {
        setIsVisible(false);
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  if (!isVisible) return null;

  return (
    <div className={styles.stickyBar}>
      <a href={`tel:${SITE_CONFIG.contact.phone.replace(/-/g, '')}`} className={styles.callBtn}>
        <FaPhoneAlt />
        <span>שיחה דחופה</span>
      </a>
      <a href={SITE_CONFIG.links.whatsapp} className={styles.whatsappBtn} target="_blank" rel="noopener noreferrer">
        <FaWhatsapp />
        <span>שלחו הודעה</span>
      </a>
    </div>
  );
};

export default MobileStickyBar;
