import React, { useEffect, useRef, useState } from 'react';
import { FaPhone, FaWhatsapp } from 'react-icons/fa';
import {
  FiAlertCircle,
  FiCheckCircle,
  FiChevronDown,
  FiClock,
  FiHeart,
  FiMapPin,
  FiMessageSquare,
  FiPhone,
  FiShield,
  FiUser,
} from 'react-icons/fi';
import CalendlyBookingEmbed from '../../components/Booking/CalendlyBookingEmbed';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import { LandingPageConfig } from '../../data/landingPagesConfig';
import { useLandingPageAnalytics } from '../../hooks/useLandingPageAnalytics';
import styles from './LandingPageTemplate.module.css';

interface LandingPageTemplateProps {
  config: LandingPageConfig;
}

const renderTrustIcon = (iconName: string) => {
  switch (iconName) {
    case 'map-pin':
      return <FiMapPin className={styles.trustIcon} aria-hidden="true" />;
    case 'clock':
      return <FiClock className={styles.trustIcon} aria-hidden="true" />;
    case 'shield':
      return <FiShield className={styles.trustIcon} aria-hidden="true" />;
    case 'user':
      return <FiUser className={styles.trustIcon} aria-hidden="true" />;
    case 'heart':
      return <FiHeart className={styles.trustIcon} aria-hidden="true" />;
    default:
      return <FiCheckCircle className={styles.trustIcon} aria-hidden="true" />;
  }
};

const renderPainIcon = (iconName?: string) => {
  switch (iconName) {
    case 'message':
      return <FiMessageSquare aria-hidden="true" />;
    case 'heart':
      return <FiHeart aria-hidden="true" />;
    case 'clock':
      return <FiClock aria-hidden="true" />;
    case 'user':
      return <FiUser aria-hidden="true" />;
    case 'shield':
      return <FiShield aria-hidden="true" />;
    default:
      return <FiAlertCircle aria-hidden="true" />;
  }
};

export const LandingPageTemplate: React.FC<LandingPageTemplateProps> = ({ config }) => {
  const [isBookingInView, setIsBookingInView] = useState(false);
  const [openFaqs, setOpenFaqs] = useState<Record<number, boolean>>({ 0: true, 1: true });
  const bookingRef = useRef<HTMLDivElement>(null);

  const {
    trackCtaClick,
    trackSecondaryCtaClick,
    trackPhoneClick,
    trackWhatsappClick,
    trackFaqInteraction,
  } = useLandingPageAnalytics({
    variantId: 'A',
    landingPagePath: config.slug,
    landingPageType: config.landingPageType,
    serviceType: config.serviceType,
  });

  const whatsappPhone = SITE_CONFIG.contact.whatsapp;
  const whatsappUrl = `https://wa.me/${whatsappPhone}?text=${encodeURIComponent(
    config.hero.prefilledWhatsappMessage,
  )}`;
  const cleanPhone = SITE_CONFIG.contact.phone.replace(/-/g, '');

  const scrollToBooking = (location: string) => {
    trackCtaClick('קביעת פגישה', location);
    if (bookingRef.current) {
      bookingRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsBookingInView(entry.isIntersecting);
      },
      { threshold: 0.15 },
    );

    if (bookingRef.current) {
      observer.observe(bookingRef.current);
    }

    return () => {
      observer.disconnect();
    };
  }, []);

  const schemaData = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Service',
        '@id': `${config.meta.canonicalUrl}#service`,
        name: config.schema.serviceName,
        alternateName: config.schema.alternateName || config.schema.serviceName,
        serviceType: config.schema.serviceType,
        description: config.schema.description,
        url: config.meta.canonicalUrl,
        ...(config.meta.image ? { image: `${SITE_CONFIG.url}${config.meta.image}` } : {}),
        provider: {
          '@type': 'LocalBusiness',
          '@id': `${SITE_CONFIG.url}/#business`,
          name: 'קשר - שירה סהרוני',
          url: SITE_CONFIG.url,
          telephone: SITE_CONFIG.contact.phone,
        },
        areaServed: config.schema.areaServed.map((area) => {
          let type = 'City';
          if (area.includes('אונליין') || area.includes('ישראל')) {
            type = 'Country';
          } else if (area.includes('השפלה') || area.includes('הדרום') || area.includes('גדרות')) {
            type = 'AdministrativeArea';
          }
          return {
            '@type': type,
            name: area,
          };
        }),
        offers: {
          '@type': 'Offer',
          price: String(config.pricing.amount),
          priceCurrency: config.pricing.currency,
          url: config.meta.canonicalUrl,
        },
      },
      {
        '@type': 'BreadcrumbList',
        '@id': `${config.meta.canonicalUrl}#breadcrumb`,
        itemListElement: [
          {
            '@type': 'ListItem',
            position: 1,
            name: 'עמוד הבית',
            item: SITE_CONFIG.url,
          },
          {
            '@type': 'ListItem',
            position: 2,
            name: config.meta.title.split('|')[0].trim(),
            item: config.meta.canonicalUrl,
          },
        ],
      },
    ],
  };

  return (
    <main
      id="main-content"
      className={styles.page}
      data-analytics-service-type={config.serviceType}
      data-analytics-landing-page-type={config.landingPageType}
      data-analytics-variant-id="A"
    >
      <MetaTags
        title={config.meta.title}
        description={config.meta.description}
        canonical={config.meta.canonicalUrl}
        image={config.meta.image}
        robots={config.meta.robots}
        noIndex={Boolean(config.meta.noIndex || config.meta.robots?.includes('noindex'))}
      />
      <SchemaOrg data={schemaData} />

      {/* 1. Distraction-Free Header */}
      <header className={styles.header}>
        <div className={`container ${styles.headerInner}`}>
          <a href="/" className={styles.brand} aria-label="מעבר לדף הבית של שירה סהרוני">
            <img
              src="/logo-kesher.svg"
              alt="קשר - שירה סהרוני"
              className={styles.brandLogo}
              width="40"
              height="40"
            />
            <div className={styles.brandText}>
              <span className={styles.brandTitle}>שירה סהרוני</span>
              <span className={styles.brandSubtitle}>קשר | ייעוץ זוגי והנחיית הורים</span>
            </div>
          </a>

          <div className={styles.headerActions}>
            <a
              href={`tel:${cleanPhone}`}
              className={styles.phoneCallBtn}
              onClick={() => trackPhoneClick('header')}
              aria-label="חיוג טלפוני לשירה סהרוני"
            >
              <FiPhone aria-hidden="true" />
            </a>
            <button
              type="button"
              className={styles.headerCtaBtn}
              onClick={() => scrollToBooking('header')}
            >
              קביעת פגישה
            </button>
          </div>
        </div>
      </header>

      {/* 2. Above-The-Fold Hero Section */}
      <section className={styles.hero} aria-labelledby="hero-title" data-analytics-location="hero">
        <div className={`container ${styles.heroGrid}`}>
          <div className={styles.heroContent}>
            <div className={styles.heroBadge}>
              <FiCheckCircle aria-hidden="true" />
              <span>{config.hero.badge}</span>
            </div>

            <h1 id="hero-title" className={styles.heroTitle}>
              {config.hero.headline}
            </h1>

            <p className={styles.heroSubtitle}>
              {config.hero.subheadline}
            </p>

            <div className={styles.heroCtaGroup}>
              <button
                type="button"
                className={styles.primaryCta}
                onClick={() => scrollToBooking('hero')}
              >
                <FiCheckCircle aria-hidden="true" />
                <span>{config.hero.primaryCtaText}</span>
              </button>

              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.secondaryWhatsappCta}
                onClick={() => trackWhatsappClick('hero')}
                aria-label="התייעצות מהירה בוואטסאפ עם שירה סהרוני"
              >
                <FaWhatsapp aria-hidden="true" />
                <span>{config.hero.whatsappCtaText}</span>
              </a>

              <a
                href={`tel:${cleanPhone}`}
                className={styles.phoneCallHeroBtn}
                onClick={() => trackPhoneClick('hero')}
                aria-label="חיוג טלפוני ישיר"
              >
                <FaPhone aria-hidden="true" />
                <span>שיחה ישירה: {SITE_CONFIG.contact.phone}</span>
              </a>
            </div>

            <div className={styles.heroTrustRow} aria-label="נקודות אמון ומיקום">
              {config.hero.trustPoints.map((point, index) => (
                <div key={index} className={styles.trustItem}>
                  {renderTrustIcon(point.icon)}
                  <span>{point.text}</span>
                </div>
              ))}
            </div>
          </div>

          <div className={styles.heroImageWrapper}>
            <img
              src={config.bio.image || '/images/shira-saharoni-sea.webp'}
              alt={`${config.bio.name} - ${config.bio.role}`}
              className={styles.heroImage}
              width="400"
              height="500"
              fetchPriority="high"
            />
            <div className={styles.heroImageBadge}>
              {config.bio.name} | {config.bio.role}
            </div>
          </div>
        </div>
      </section>

      {/* 3. Acute Pain Points (Recognition) */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>{config.painPoints.sectionTitle}</h2>
            <p className={styles.sectionSubtitle}>{config.painPoints.sectionSubtitle}</p>
          </div>

          <div className={styles.painGrid}>
            {config.painPoints.items.map((item, index) => (
              <div key={index} className={styles.painCard}>
                <div className={styles.painIconWrapper}>
                  {renderPainIcon(item.icon)}
                </div>
                <h3 className={styles.painTitle}>{item.title}</h3>
                <p className={styles.painDesc}>{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 4. Practical Approach (3 Calming Steps) */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>{config.approach.sectionTitle}</h2>
            <p className={styles.sectionSubtitle}>{config.approach.sectionSubtitle}</p>
          </div>

          <div className={styles.stepsGrid}>
            {config.approach.steps.map((step) => (
              <div key={step.stepNumber} className={styles.stepCard}>
                <div className={styles.stepBadgeRow}>
                  <div className={styles.stepNumber}>{step.stepNumber}</div>
                  <div className={styles.timeBadge}>{step.timeBadge}</div>
                </div>
                <h3 className={styles.stepTitle}>{step.title}</h3>
                <p className={styles.stepDesc}>{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 5. Contextual parent / canonical service link */}
      <section className={styles.relatedServiceSection} aria-label="שירות קשור">
        <div className="container">
          <div className={styles.relatedServiceCard}>
            <div>
              <h2 className={styles.relatedServiceTitle}>{config.relatedService.title}</h2>
              <p className={styles.relatedServiceText}>{config.relatedService.description}</p>
            </div>
            <a
              href={config.relatedService.href}
              className={styles.relatedServiceLink}
              data-analytics-location="related_service"
              onClick={() =>
                trackSecondaryCtaClick(config.relatedService.linkText, 'related_service')
              }
            >
              {config.relatedService.linkText}
              <span aria-hidden="true">←</span>
            </a>
          </div>
        </div>
      </section>

      {/* 6. Bio Section (Grounding & Human Connection) */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.bioCard}>
            <img
              src={config.bio.image}
              alt={`${config.bio.name} - ${config.bio.role}`}
              className={styles.bioAvatar}
              width="140"
              height="140"
              loading="lazy"
            />
            <div>
              <h2 className={styles.bioName}>{config.bio.name}</h2>
              <div className={styles.bioRole}>{config.bio.role}</div>
              <p className={styles.bioText}>{config.bio.description}</p>
              <div className={styles.credentialsList}>
                {config.bio.credentials.map((cred, idx) => (
                  <span key={idx} className={styles.credentialPill}>
                    ✓ {cred}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 7. Pricing Card & Interactive Booking Embed */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.priceCard}>
            <h2 className={styles.priceTitle}>{config.pricing.title}</h2>
            <div className={styles.priceDuration}>{config.pricing.duration}</div>
            <div className={styles.priceAmount}>{config.pricing.amount} ₪</div>
            <p className={styles.priceNote}>{config.pricing.description}</p>
          </div>

          <div
            ref={bookingRef}
            id="booking"
            className={styles.bookingContainer}
            data-analytics-location="booking_help"
          >
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>{config.booking.title}</h2>
              <p className={styles.sectionSubtitle}>{config.booking.subtitle}</p>
            </div>

            <CalendlyBookingEmbed
              ariaLabel={config.booking.calendlyAriaLabel}
              bookingPagePath={config.slug}
              serviceType={config.serviceType}
              landingPageType={config.landingPageType}
              variantId="A"
              value={config.pricing.amount}
              currency={config.pricing.currency}
            />

            <div className={styles.bookingHelp}>
              <span>מעדיפים לשאול שאלה לפני שקובעים?</span>
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => trackWhatsappClick('booking_help')}
              >
                <FaWhatsapp aria-hidden="true" />
                כתבו לשירה ב-WhatsApp
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* 8. Objection-Handling FAQ Accordion */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>{config.faq.sectionTitle}</h2>
          </div>

          <div className={styles.faqList}>
            {config.faq.items.map((item, index) => (
              <div key={item.question} className={styles.faqItem}>
                <details
                  className={styles.faqDetails}
                  open={Boolean(openFaqs[index])}
                  onToggle={(e) => {
                    const isOpen = (e.target as HTMLDetailsElement).open;
                    setOpenFaqs((prev) => ({ ...prev, [index]: isOpen }));
                    if (isOpen) {
                      trackFaqInteraction(index);
                    }
                  }}
                >
                  <summary className={styles.faqSummary}>
                    <span>{item.question}</span>
                    <FiChevronDown className={styles.faqChevron} aria-hidden="true" />
                  </summary>
                  <div className={styles.faqAnswer}>
                    <p>{item.answer}</p>
                  </div>
                </details>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 9. Closing Reassurance CTA */}
      <section className={styles.closingCta} data-analytics-location="closing_cta">
        <div className="container">
          <h2 className={styles.closingTitle}>{config.closingCta.title}</h2>
          <p className={styles.closingSubtitle}>{config.closingCta.subtitle}</p>
          <div className={styles.closingCtas}>
            <button
              type="button"
              className={styles.closingPrimaryBtn}
              onClick={() => scrollToBooking('closing_cta')}
            >
              <FiCheckCircle aria-hidden="true" />
              <span>{config.closingCta.primaryCtaText}</span>
            </button>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.closingWhatsappBtn}
              onClick={() => trackWhatsappClick('closing_cta')}
            >
              <FaWhatsapp aria-hidden="true" />
              <span>{config.closingCta.whatsappCtaText}</span>
            </a>
          </div>
        </div>
      </section>

      {/* 10. Minimalist Footer */}
      <footer className={styles.footer}>
        <div className={`container ${styles.footerInner}`}>
          <div className={styles.footerLinks}>
            <a href="/">דף הבית</a>
            <a href="/about">אודות שירה סהרוני</a>
            <a href="/services/couples">ייעוץ זוגי</a>
            <a href="/services/parenting">הדרכת הורים</a>
            <a href="/services/mediation">גישור</a>
            <a href="/privacy">מדיניות פרטיות</a>
            <a href="/accessibility">הצהרת נגישות</a>
            <a href="/terms">תנאי שימוש</a>
          </div>
          <p className={styles.copyright}>
            © {new Date().getFullYear()} שירה סהרוני — קשר. כל הזכויות שמורות.
          </p>
        </div>
      </footer>

      {/* 11. Mobile Sticky Bottom Bar */}
      {!isBookingInView && (
        <div
          className={styles.mobileStickyBar}
          role="region"
          aria-label="סרגל יצירת קשר מהיר"
          data-analytics-location="mobile_sticky"
        >
          <a
            href={`tel:${cleanPhone}`}
            className={styles.stickyPhoneBtn}
            onClick={() => trackPhoneClick('mobile_sticky')}
            aria-label="חיוג טלפוני לשירה סהרוני"
          >
            <FaPhone aria-hidden="true" />
          </a>
          <a
            href={whatsappUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.stickyWhatsappBtn}
            onClick={() => trackWhatsappClick('mobile_sticky')}
            aria-label="הודעת WhatsApp לשירה סהרוני"
          >
            <FaWhatsapp aria-hidden="true" />
            <span>WhatsApp</span>
          </a>
          <button
            type="button"
            className={styles.stickyBookingBtn}
            onClick={() => scrollToBooking('mobile_sticky')}
            aria-label="קביעת פגישת ייעוץ"
          >
            <FiCheckCircle aria-hidden="true" />
            <span>קביעת פגישה</span>
          </button>
        </div>
      )}
    </main>
  );
};

export default LandingPageTemplate;
