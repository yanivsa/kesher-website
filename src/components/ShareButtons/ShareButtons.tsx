import { useState, useSyncExternalStore } from 'react';
import { FaFacebookF, FaWhatsapp } from 'react-icons/fa';
import { FiCheck, FiCopy, FiShare2 } from 'react-icons/fi';
import styles from './ShareButtons.module.css';

type ShareMethod = 'Facebook' | 'WhatsApp' | 'CopyLink' | 'Native';
type SharePlacement = 'article_top' | 'article_bottom';

interface ShareButtonsProps {
  title: string;
  url: string;
  itemId: string;
  placement: SharePlacement;
}

const trackShare = (method: ShareMethod, itemId: string, placement: SharePlacement) => {
  if (typeof window === 'undefined') return;

  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push({
    event: 'share',
    method,
    content_type: 'article',
    item_id: itemId,
    share_placement: placement,
  });
};

const openExternalShare = (shareUrl: string) => {
  window.open(shareUrl, '_blank', 'noopener,noreferrer');
};

const copyToClipboard = async (value: string) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand('copy');
  textarea.remove();

  if (!copied) throw new Error('Clipboard copy failed');
};

const subscribeToShareCapability = () => () => {};
const getShareCapability = () => typeof navigator !== 'undefined' && typeof navigator.share === 'function';
const getServerShareCapability = () => false;

const ShareButtons = ({ title, url, itemId, placement }: ShareButtonsProps) => {
  const [copied, setCopied] = useState(false);
  const [status, setStatus] = useState('');
  const canNativeShare = useSyncExternalStore(
    subscribeToShareCapability,
    getShareCapability,
    getServerShareCapability,
  );
  const shareMessage = `${title}\n${url}`;

  const shareWhatsApp = () => {
    trackShare('WhatsApp', itemId, placement);
    openExternalShare(`https://api.whatsapp.com/send?text=${encodeURIComponent(shareMessage)}`);
  };

  const shareFacebook = () => {
    trackShare('Facebook', itemId, placement);
    openExternalShare(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`);
  };

  const handleCopy = async () => {
    try {
      await copyToClipboard(url);
      trackShare('CopyLink', itemId, placement);
      setCopied(true);
      setStatus('הקישור הועתק');
      window.setTimeout(() => {
        setCopied(false);
        setStatus('');
      }, 2200);
    } catch {
      setStatus('לא הצלחנו להעתיק את הקישור. אפשר להעתיק אותו משורת הכתובת.');
    }
  };

  const handleNativeShare = async () => {
    if (!canNativeShare) return;

    try {
      await navigator.share({ title, url });
      trackShare('Native', itemId, placement);
      setStatus('אפשרויות השיתוף נפתחו');
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      setStatus('השיתוף לא הושלם. אפשר לבחור WhatsApp, Facebook או העתקת קישור.');
    }
  };

  return (
    <section className={styles.share} aria-label="שיתוף המאמר">
      <span className={styles.label}>שתפו את המאמר:</span>
      <div className={styles.actions}>
        <button
          type="button"
          className={`${styles.button} ${styles.whatsapp}`}
          onClick={shareWhatsApp}
          aria-label="שיתוף המאמר ב-WhatsApp"
        >
          <FaWhatsapp aria-hidden="true" />
          <span>WhatsApp</span>
        </button>
        <button
          type="button"
          className={`${styles.button} ${styles.facebook}`}
          onClick={shareFacebook}
          aria-label="שיתוף המאמר ב-Facebook"
        >
          <FaFacebookF aria-hidden="true" />
          <span>Facebook</span>
        </button>
        <button
          type="button"
          className={styles.button}
          onClick={handleCopy}
          aria-label="העתקת קישור למאמר"
        >
          {copied ? <FiCheck aria-hidden="true" /> : <FiCopy aria-hidden="true" />}
          <span>{copied ? 'הועתק' : 'העתק קישור'}</span>
        </button>
        {canNativeShare && (
          <button
            type="button"
            className={`${styles.button} ${styles.native}`}
            onClick={handleNativeShare}
            aria-label="פתיחת אפשרויות השיתוף במכשיר"
          >
            <FiShare2 aria-hidden="true" />
            <span>שיתוף</span>
          </button>
        )}
      </div>
      <span className={styles.status} role="status" aria-live="polite">{status}</span>
    </section>
  );
};

export default ShareButtons;
