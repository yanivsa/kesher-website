import React, { useEffect, useState } from 'react';
import { FaWhatsapp } from 'react-icons/fa';
import { FiCalendar } from 'react-icons/fi';
import { Link, useLocation } from 'react-router-dom';
import { SITE_CONFIG } from '../../constants/siteConfig';
import { isParentingCoordinationPath, PARENTING_COORDINATION_CONTACT_URL, PARENTING_COORDINATION_WHATSAPP_MESSAGE } from '../../lib/parentingCoordination';
import styles from './MobileStickyBar.module.css';

const MobileStickyBar: React.FC = () => {
  const [isVisible, setIsVisible] = useState(false);
  const { pathname, search } = useLocation();
  const coordinationInquiry = isParentingCoordinationPath(pathname, search);
  const contactUrl = coordinationInquiry ? PARENTING_COORDINATION_CONTACT_URL : SITE_CONFIG.links.appointment;
  const whatsappUrl = coordinationInquiry
    ? `https://wa.me/${SITE_CONFIG.contact.whatsapp}?text=${encodeURIComponent(PARENTING_COORDINATION_WHATSAPP_MESSAGE)}`
    : SITE_CONFIG.links.whatsapp;

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
      <Link to={contactUrl} className={styles.appointmentBtn} aria-label={coordinationInquiry ? "בירור התאמה לתיאום הורי" : "קביעת פגישת ייעוץ"}>
        <FiCalendar aria-hidden="true" />
        <span>{coordinationInquiry ? "בירור התאמה" : "קביעת פגישה"}</span>
      </Link>
      <a href={whatsappUrl} className={styles.whatsappBtn} target="_blank" rel="noopener noreferrer" aria-label="שלחו הודעת וואטסאפ">
        <FaWhatsapp aria-hidden="true" />
        <span>שלחו הודעה</span>
      </a>
    </div>
  );
};

export default MobileStickyBar;
