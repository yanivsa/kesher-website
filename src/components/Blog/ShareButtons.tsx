import React, { useState } from 'react';
import { FaWhatsapp, FaFacebookF } from 'react-icons/fa';
import { FiCopy, FiCheck } from 'react-icons/fi';
import styles from './ShareButtons.module.css';

interface ShareButtonsProps {
  title: string;
  url?: string;
}

const ShareButtons: React.FC<ShareButtonsProps> = ({ title, url }) => {
  const [copied, setCopied] = useState(false);
  const shareUrl = url || (typeof window !== 'undefined' ? window.location.href : '');

  const whatsappText = encodeURIComponent(`מאמר מומלץ מאת שירה סהרוני: "${title}"\n${shareUrl}`);
  const whatsappLink = `https://wa.me/?text=${whatsappText}`;
  const facebookLink = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`;

  const handleCopy = async () => {
    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(shareUrl);
        setCopied(true);
        setTimeout(() => setCopied(false), 3000);
      }
    } catch {
      // Fallback
    }
  };

  return (
    <div className={styles.shareContainer} aria-label="שיתוף המאמר">
      <h4 className={styles.shareTitle}>שתפו את המאמר עם מי שזה יכול לעזור לו:</h4>
      <div className={styles.buttonsGroup}>
        <a 
          href={whatsappLink} 
          target="_blank" 
          rel="noopener noreferrer" 
          className={`${styles.shareBtn} ${styles.whatsappBtn}`}
          aria-label="שתפו בוואטסאפ"
        >
          <FaWhatsapp aria-hidden="true" />
          שתפו בוואטסאפ
        </a>
        <a 
          href={facebookLink} 
          target="_blank" 
          rel="noopener noreferrer" 
          className={`${styles.shareBtn} ${styles.facebookBtn}`}
          aria-label="שתפו בפייסבוק"
        >
          <FaFacebookF aria-hidden="true" />
          שתפו בפייסבוק
        </a>
        <button 
          type="button" 
          onClick={handleCopy} 
          className={`${styles.shareBtn} ${styles.copyBtn}`}
          aria-label="העתקת קישור למאמר"
        >
          {copied ? <FiCheck aria-hidden="true" /> : <FiCopy aria-hidden="true" />}
          {copied ? 'הקישור הועתק!' : 'העתקת קישור'}
        </button>
      </div>
    </div>
  );
};

export default ShareButtons;
