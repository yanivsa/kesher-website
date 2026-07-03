import React from 'react';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './FloatingWhatsApp.module.css';

const FloatingWhatsApp: React.FC = () => {
  return (
    <a 
      href={SITE_CONFIG.links.whatsapp} 
      className={styles.button} 
      target="_blank" 
      rel="noopener noreferrer"
      aria-label="יצירת קשר בוואטסאפ"
    >
      <svg viewBox="0 0 24 24" className={styles.icon}>
        <path fill="currentColor" d="M12.01 2.01c-5.52 0-9.99 4.47-9.99 9.99 0 1.76.46 3.42 1.26 4.87L2 22l5.3-1.39c1.4.74 3 1.16 4.71 1.16 5.52 0 9.99-4.47 9.99-9.99 0-5.52-4.47-9.99-9.99-9.99zm5.95 14.12c-.25.7-1.44 1.34-1.99 1.41-.53.07-1.04.28-3.41-.66-2.85-1.14-4.69-4.04-4.83-4.23-.14-.19-1.14-1.51-1.14-2.88 0-1.37.71-2.04.96-2.31.25-.27.53-.34.71-.34.18 0 .36.01.52.01.17 0 .4-.06.63.5.23.56.78 1.9.85 2.04.07.14.12.31.02.5-.09.19-.14.3-.28.46-.14.16-.3.37-.43.5-.14.14-.28.29-.12.57.16.28.71 1.17 1.52 1.89.81.72 1.49 1.12 1.77 1.26.28.14.44.12.61-.07.17-.19.71-.83.9-.11.19.14.39.38.56.59.17.21.34.42.5.55.16.13.34.13.59.02.25-.11 1.48-.61 1.69-.73.21-.12.34-.18.47-.07.13.11.33.64.25.75z"/>
      </svg>
    </a>
  );
};

export default FloatingWhatsApp;
