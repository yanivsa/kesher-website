import React from 'react';
import { Link } from 'react-router-dom';
import { FaPhone, FaWhatsapp } from 'react-icons/fa';
import { FiArrowLeft, FiHeart } from 'react-icons/fi';
import { SITE_CONFIG } from '../../constants/siteConfig';
import { pushAnalyticsEvent } from '../../lib/analytics';
import styles from './LandingCalloutBanner.module.css';

export type LandingTarget =
  | 'couples_crisis'
  | 'parenting_adhd'
  | 'couples_mediation';

export interface LandingCalloutBannerProps {
  target?: LandingTarget;
  title?: string;
  subtitle?: string;
  ctaText?: string;
  linkUrl?: string;
  badge?: string;
  whatsappMessage?: string;
  className?: string;
}

const DEFAULTS: Record<LandingTarget, {
  badge: string;
  title: string;
  subtitle: string;
  linkUrl: string;
  ctaText: string;
  whatsappMessage: string;
}> = {
  couples_crisis: {
    badge: 'ייעוץ זוגי ממוקד משבר | אשדוד ובזום',
    title: 'מרגישים שהשיחות חוזרות על עצמן ונגמרות בכעס או בריחוק?',
    subtitle: 'כשאותו דפוס של ריב, שתיקה או ריחוק חוזר, אפשר לקבל מסגרת מסודרת להבנת המעגל ולבחירת צעדים מעשיים להמשך.',
    linkUrl: '/services/couples/crisis',
    ctaText: 'למידע על ייעוץ זוגי במשבר',
    whatsappMessage: 'היי שירה, קראתי מאמר באתר ואשמח להתייעץ לגבי ייעוץ זוגי במשבר.',
  },
  parenting_adhd: {
    badge: 'הדרכת הורים ל-ADHD | אשדוד ובזום',
    title: 'מתמודדים עם קשיי קשב, התארגנות בוקר או התפרצויות זעם?',
    subtitle: 'קשיי קשב יכולים להפוך בוקר, מסכים ומעברים למוקדי חיכוך. הדרכת הורים ממוקדת מציעה כלים מעשיים לשגרה, גבולות ותקשורת.',
    linkUrl: '/parenting-adhd-ashdod',
    ctaText: 'לפרטים על הדרכת הורים ל-ADHD באשדוד',
    whatsappMessage: 'היי שירה, קראתי מאמר באתר ואשמח להתייעץ לגבי הדרכת הורים לקשב וריכוז.',
  },
  couples_mediation: {
    badge: 'גישור זוגי ושלום בית | אשדוד ובזום',
    title: 'נמצאים בצומת דרכים ורוצים להגיע להסכמות בכבוד?',
    subtitle: 'מתווה מקצועי ומכבד לבירור הסכמות סביב שלום בית או פרידה, תוך התייחסות לצרכים של בני הזוג והילדים.',
    linkUrl: '/couples-mediation-ashdod',
    ctaText: 'למידע על גישור ושלום בית באשדוד',
    whatsappMessage: 'היי שירה, קראתי מאמר באתר ואשמח להתייעץ לגבי גישור זוגי והסכם שלום בית.',
  },
};

export const LandingCalloutBanner: React.FC<LandingCalloutBannerProps> = ({
  target = 'couples_crisis',
  title,
  subtitle,
  ctaText,
  linkUrl,
  badge,
  whatsappMessage,
  className = '',
}) => {
  const preset = DEFAULTS[target] || DEFAULTS.couples_crisis;

  const resolvedBadge = badge || preset.badge;
  const resolvedTitle = title || preset.title;
  const resolvedSubtitle = subtitle || preset.subtitle;
  const resolvedLinkUrl = linkUrl || preset.linkUrl;
  const resolvedCtaText = ctaText || preset.ctaText;
  const resolvedWhatsappMessage = whatsappMessage || preset.whatsappMessage;

  const whatsappUrl = `https://wa.me/${SITE_CONFIG.contact.whatsapp}?text=${encodeURIComponent(
    resolvedWhatsappMessage,
  )}`;
  const cleanPhone = SITE_CONFIG.contact.phone.replace(/-/g, '');

  const handleLinkClick = () => {
    pushAnalyticsEvent('primary_cta_click', {
      cta_name: resolvedCtaText,
      cta_location: 'blog_landing_callout',
      target_url: resolvedLinkUrl,
    });
  };

  const handleWhatsappClick = () => {
    pushAnalyticsEvent('whatsapp_click', {
      cta_location: 'blog_landing_callout',
      target: target,
    });
  };

  const handlePhoneClick = () => {
    pushAnalyticsEvent('phone_click', {
      cta_location: 'blog_landing_callout',
      target: target,
    });
  };

  return (
    <aside
      className={`${styles.calloutBanner} ${className}`.trim()}
      aria-label={resolvedTitle}
    >
      <div className={styles.calloutHeader}>
        <span className={styles.calloutBadge}>
          <FiHeart aria-hidden="true" />
          {resolvedBadge}
        </span>
      </div>

      <h3 className={styles.calloutTitle}>{resolvedTitle}</h3>
      <p className={styles.calloutSubtitle}>{resolvedSubtitle}</p>

      <div className={styles.calloutActions}>
        <Link
          to={resolvedLinkUrl}
          className={styles.primaryLinkBtn}
          onClick={handleLinkClick}
        >
          <span>{resolvedCtaText}</span>
          <FiArrowLeft aria-hidden="true" />
        </Link>

        <a
          href={whatsappUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.whatsappBtn}
          onClick={handleWhatsappClick}
          aria-label="התייעצות מהירה בוואטסאפ עם שירה סהרוני"
        >
          <FaWhatsapp aria-hidden="true" />
          <span>התייעצות בוואטסאפ</span>
        </a>

        <a
          href={`tel:${cleanPhone}`}
          className={styles.phoneCallBtn}
          onClick={handlePhoneClick}
          aria-label="שיחה טלפונית ישירה לשירה סהרוני"
        >
          <FaPhone aria-hidden="true" />
          <span>{SITE_CONFIG.contact.phone}</span>
        </a>
      </div>
    </aside>
  );
};

export default LandingCalloutBanner;
