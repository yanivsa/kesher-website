import React, { useEffect, useState } from 'react';
import { FaWhatsapp } from 'react-icons/fa';
import { FiCalendar } from 'react-icons/fi';
import { Link } from 'react-router-dom';
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
      <Link to={SITE_CONFIG.links.appointment} className={styles.appointmentBtn} aria-label="קביעת פגישת ייעוץ">
        <FiCalendar aria-hidden="true" />
        <span>קביעת פגישה</span>
      </Link>
      <a href={SITE_CONFIG.links.whatsapp} className={styles.whatsappBtn} target="_blank" rel="noopener noreferrer" aria-label="שלחו הודעת וואטסאפ">
        <FaWhatsapp aria-hidden="true" />
        <span>שלחו הודעה</span>
      </a>
    </div>
  );
};

export default MobileStickyBar;
