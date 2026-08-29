import React, { useState, useEffect, useRef } from 'react';
import {
  FiClock,
  FiShield,
  FiMapPin,
  FiCheckCircle,
  FiHelpCircle,
  FiCompass,
  FiPhone,
  FiChevronDown,
  FiChevronUp,
  FiInfo,
  FiCalendar,
  FiUserCheck,
} from 'react-icons/fi';
import { FaWhatsapp } from 'react-icons/fa';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import CalendlyBookingEmbed from '../../../components/Booking/CalendlyBookingEmbed';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import { useLandingPageAnalytics } from '../../../hooks/useLandingPageAnalytics';
import styles from './CouplesBeforeSeparationPage.module.css';

interface FAQItem {
  q: string;
  a: string;
}

const FAQS: FAQItem[] = [
  {
    q: 'האם חייבים ששני בני הזוג יגיעו לפגישה?',
    a: 'מומלץ מאוד להגיע כזוג כדי ששני בני הזוג יוכלו להשמיע את נקודת מבטם. עם זאת, אם אחד מבני הזוג מתלבט או חושש, ניתן לפנות לשירה ב-WhatsApp ולהתייעץ מראש לפני ההחלטה.',
  },
  {
    q: 'מה אם אחד מבני הזוג לא רוצה טיפול או כבר מיואש?',
    a: 'זהו מצב שכיח מאוד בצמתים כאלה. הפגישה אינה מיועדת לשפוט, להכריע מי אשם או לכפות תהליך ארוך, אלא להניח את הפערים והחששות על השולחן בצורה מכבדת ולבדוק ללא לחץ האם קיימת דרך אחרת.',
  },
  {
    q: 'האם התהליך מתאים לפני החלטה על פרידה?',
    a: 'כן. לפני שמקבלים החלטות כבדות או לפני שמפרקים את הקשר, מומלץ לעצור לבירור זוגי רגוע. הפגישה מעניקה מרחב להבין אם ומה ניתן לשנות, ולבחון את המשך הדרך באחריות ובבהירות.',
  },
  {
    q: 'האם הפגישה דיסקרטית?',
    a: 'בהחלט. כל פגישה מתקיימת בדיסקרטיות מלאה ובמרחב פרטי ומכבד בהתאם לכללי האתיקה המקצועית.',
  },
  {
    q: 'האם אפשר לקיים את הפגישה אונליין?',
    a: 'כן. לצד הקליניקה באשדוד, ניתן לקיים את פגישת הבירור והייעוץ אונליין ב-Zoom.',
  },
  {
    q: 'כמה זמן נמשכת פגישה ומה המחיר?',
    a: 'פגישת בירור וייעוץ זוגי נמשכת 50 דקות מלאות. העלות היא 500 ₪ כולל מע״מ, ללא כל התחייבות מראש להמשך תהליך.',
  },
];

const CouplesBeforeSeparationPage: React.FC = () => {
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [isBookingInView, setIsBookingInView] = useState(false);
  const bookingRef = useRef<HTMLDivElement>(null);

  const {
    trackCtaClick,
    trackSecondaryCtaClick,
    trackPhoneClick,
    trackWhatsappClick,
    trackCalendlyOpen,
  } = useLandingPageAnalytics({
    variantId: 'A',
    landingPagePath: '/services/couples/before-separation',
    landingPageType: 'before_separation',
    serviceType: 'couples_before_separation',
  });

  const whatsappPhone = SITE_CONFIG.contact.phone.replace(/[^0-9]/g, '');
  const whatsappUrl = `https://wa.me/${whatsappPhone}?text=${encodeURIComponent(
    'היי שירה, אנחנו בצומת החלטה בזוגיות ונשמח לבדוק פגישת בירור זוגי.',
  )}`;

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsBookingInView(entry.isIntersecting);
      },
      { threshold: 0.15 }
    );

    if (bookingRef.current) {
      observer.observe(bookingRef.current);
    }

    return () => {
      observer.disconnect();
    };
  }, []);

  const toggleFaq = (index: number) => {
    setOpenFaq((prev) => (prev === index ? null : index));
  };

  const scrollToBooking = (location: string) => {
    trackCtaClick('קביעת פגישה', location);
    trackCalendlyOpen();
    if (bookingRef.current) {
      bookingRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const schemaData = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Service',
        name: 'בירור וייעוץ זוגי לפני החלטות כבדות | שירה סהרוני',
        serviceType: 'Couples Discernment and Counseling',
        provider: {
          '@type': 'Person',
          name: 'שירה סהרוני',
          jobTitle: 'יועצת זוגית, מנחת הורים ומגשרת מוסמכת',
          url: 'https://kesher.saharoni.com',
          telephone: '+972-50-2763802',
        },
        areaServed: [
          { '@type': 'City', name: 'אשדוד' },
          { '@type': 'Country', name: 'ישראל' },
        ],
        offers: {
          '@type': 'Offer',
          price: '500',
          priceCurrency: 'ILS',
          availability: 'https://schema.org/InStock',
        },
      },
      {
        '@type': 'FAQPage',
        mainEntity: FAQS.map((faq) => ({
          '@type': 'Question',
          name: faq.q,
          acceptedAnswer: {
            '@type': 'Answer',
            text: faq.a,
          },
        })),
      },
    ],
  };

  return (
    <main id="main-content" className={styles.page}>
      <MetaTags
        title="לפני שמקבלים החלטה כבדה – בירור זוגי רגוע | שירה סהרוני"
        description="לפני שמפרקים את הקשר, עצירה לבירור זוגי רגוע וממוקד. מרחב להבין אם ומה ניתן לשנות ביחסים בטרם החלטות כבדות. 50 דקות, 500 ₪ באשדוד או בזום."
        canonical="https://kesher.saharoni.com/services/couples/before-separation"
      />
      <SchemaOrg data={schemaData} />

      {/* Header */}
      <header className={styles.header}>
        <div className={`container ${styles.headerInner}`}>
          <a href="/" className={styles.brand} aria-label="מעבר לדף הבית של שירה סהרוני">
            <img src="/logo-kesher.svg" alt="קשר - שירה סהרוני" className={styles.brandLogo} width="40" height="40" />
            <div className={styles.brandText}>
              <span className={styles.brandTitle}>שירה סהרוני</span>
              <span className={styles.brandSubtitle}>בירור זוגי לפני החלטות כבדות | אשדוד ואונליין</span>
            </div>
          </a>

          <div className={styles.headerActions}>
            <a
              href={`tel:${whatsappPhone}`}
              className={styles.phoneCallBtn}
              onClick={() => trackPhoneClick()}
              aria-label="התקשרות טלפונית לשירה סהרוני"
            >
              <FiPhone aria-hidden="true" />
            </a>
            <button
              type="button"
              className={styles.headerCtaBtn}
              onClick={() => scrollToBooking('header')}
            >
              קביעת פגישת ייעוץ
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className={styles.hero}>
        <div className={`container ${styles.heroContent}`}>
          <div className={styles.heroBadge}>
            <FiCompass aria-hidden="true" />
            <span>צומת החלטה זוגי – מרחב לבירור מעמיק ורגוע</span>
          </div>

          <h1 className={styles.heroTitle}>
            לפני שמקבלים החלטה כבדה – בירור זוגי רגוע וממוקד
          </h1>

          <p className={styles.heroSubtitle}>
            לפני שמפרקים את הקשר או מקבלים החלטות דרמטיות, עוצרים להבין מה קורה ביניכם. פגישת ייעוץ ובירור מעניקה מרחב להבין אם ומה ניתן לשנות ביחסים, ולבחון את האפשרויות בבהירות ובאחריות.
          </p>

          <div className={styles.heroCtaGroup}>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.primaryWhatsappCta}
              onClick={() => {
                trackSecondaryCtaClick('כתבו לי ב-WhatsApp', 'hero');
                trackWhatsappClick();
              }}
              aria-label="כתבו לי ב-WhatsApp"
            >
              <FaWhatsapp aria-hidden="true" />
              <span>כתבו לי ב-WhatsApp</span>
            </a>

            <button
              type="button"
              className={styles.secondaryBookingCta}
              onClick={() => scrollToBooking('hero_secondary')}
            >
              <FiCalendar aria-hidden="true" />
              <span>קביעת פגישת ייעוץ</span>
            </button>
          </div>

          <div className={styles.heroTrustRow}>
            <div className={styles.trustItem}>
              <FiMapPin className={styles.trustIcon} aria-hidden="true" />
              <span>אשדוד</span>
            </div>
            <div className={styles.trustItem}>
              <FiUserCheck className={styles.trustIcon} aria-hidden="true" />
              <span>אונליין ב-Zoom</span>
            </div>
            <div className={styles.trustItem}>
              <FiClock className={styles.trustIcon} aria-hidden="true" />
              <span>פגישה 50 דקות</span>
            </div>
            <div className={styles.trustItem}>
              <FiShield className={styles.trustIcon} aria-hidden="true" />
              <span>דיסקרטיות מלאה</span>
            </div>
          </div>
        </div>
      </section>

      {/* PROBLEM Section */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>כשהספקות מכבידים והעתיד לא ברור</h2>
            <p className={styles.sectionSubtitle}>
              הימצאות בצומת החלטה זוגי מלווה לרוב בעומס רגשי, בלבול וחשש מצעדים בלתי הפיכים.
            </p>
          </div>

          <div className={styles.grid3}>
            <div className={styles.clarityCard}>
              <FiHelpCircle className={styles.clarityIcon} aria-hidden="true" />
              <h3 className={styles.clarityTitle}>התלבטות האם לנסות שוב</h3>
              <p className={styles.clarityDesc}>
                תחושה שהקשר נתקע במעגל סגור, לצד רצון לבדוק באמת האם קיימת אפשרות ומוטיבציה הדדית לשינוי.
              </p>
            </div>

            <div className={styles.clarityCard}>
              <FiCompass className={styles.clarityIcon} aria-hidden="true" />
              <h3 className={styles.clarityTitle}>פערים בעמדות ובכוונות</h3>
              <p className={styles.clarityDesc}>
                מצבים שבהם אחד מבני הזוג נוטה לסיום הקשר והשני מבקש הזדמנות, ונדרש שיח כן ורגיש ללא מלחמות.
              </p>
            </div>

            <div className={styles.clarityCard}>
              <FiShield className={styles.clarityIcon} aria-hidden="true" />
              <h3 className={styles.clarityTitle}>שמירה על כבוד ועל הילדים</h3>
              <p className={styles.clarityDesc}>
                הבנה שכל החלטה שתתקבל חייבת להיעשות באחריות ובכבוד הדדי, כדי למנוע פגיעה מיותרת במשפחה.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* SOLUTION Section (3 Steps) */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>התהליך: 3 שלבים לבירור זוגי רגוע</h2>
            <p className={styles.sectionSubtitle}>
              מרחב מובנה שמביא בהירות ומאפשר לקבל החלטות מושכלות.
            </p>
          </div>

          <div className={styles.stepsGrid}>
            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>1</div>
              <h3 className={styles.stepTitle}>בירור עמדות וצרכים</h3>
              <p className={styles.stepDesc}>
                מיפוי הרגשות, החששות והציפיות של כל צד במרחב ניטרלי ומכבד, המאפשר לכל אחד להשמיע את קולו.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>2</div>
              <h3 className={styles.stepTitle}>הבנת מרחב השינוי</h3>
              <p className={styles.stepDesc}>
                בדיקה כנה של התנאים והכלים הנדרשים לשיקום התקשורת והאמון, לעומת בחינת האפשרויות במידה ומחליטים להיפרד.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>3</div>
              <h3 className={styles.stepTitle}>קבלת החלטה אחראית</h3>
              <p className={styles.stepDesc}>
                גיבוש דרך פעולה ברורה בהסכמה: יציאה לדרך של ייעוץ זוגי ממוקד או פנייה לתהליך גישור מכבד.
              </p>
            </div>
          </div>

          {/* Legal Guardrail & Professional Disclaimer */}
          <div className={styles.disclaimerBox}>
            <FiInfo className={styles.disclaimerIcon} aria-hidden="true" />
            <p className={styles.disclaimerText}>
              <strong>הבהרה מקצועית:</strong> המפגש מיועד לבירור זוגי, רגשי ותקשורתי ואינו מהווה ייעוץ משפטי, אינו מעניק חוות דעת משפטית ואינו מבטיח למנוע גירושין. שירה סהרוני היא יועצת זוגית ומגשרת מוסמכת (עורכת דין בהכשרתה). במידת הצורך בייעוץ או ייצוג משפטי, יש לפנות לעו״ד בתחום המשפחה.
            </p>
          </div>
        </div>
      </section>

      {/* WHY SHIRA Section */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.bioCard}>
            <div className={styles.bioHeader}>
              <img
                src="/images/shira-saharoni.webp"
                alt="שירה סהרוני - יועצת זוגית ומגשרת מוסמכת"
                className={styles.bioAvatar}
                width="90"
                height="90"
                loading="lazy"
              />
              <div>
                <h2 className={styles.bioName}>למה לפנות לשירה סהרוני?</h2>
                <p className={styles.bioRole}>יועצת זוגית, מנחת הורים ומגשרת מוסמכת, עורכת דין בהכשרתה</p>
              </div>
            </div>

            <p className={styles.bioText}>
              בעלת רקע כמגשרת ויועצת זוגית (עורכת דין בהכשרתי), אני פוגשת זוגות ברגעי ההכרעה הרגישים ביותר. הניסיון מלמד כי שיח רגוע ומובנה בצומת החלטה חוסך כאב רב, מאפשר הבנה עמוקה ומגן על עתיד המשפחה — בין אם מדובר בשיקום הקשר ובין אם בבניית הסכמות.
            </p>

            <div className={styles.credentialsList}>
              <span className={styles.credentialPill}>✓ יועצת זוגית מוסמכת</span>
              <span className={styles.credentialPill}>✓ מגשרת מוסמכת</span>
              <span className={styles.credentialPill}>✓ מנחת הורים מוסמכת</span>
              <span className={styles.credentialPill}>✓ עורכת דין בהכשרתה</span>
              <span className={styles.credentialPill}>✓ קליניקה באשדוד וב-Zoom</span>
            </div>
          </div>
        </div>
      </section>

      {/* PRICING & BOOKING Section */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.priceCard}>
            <h2 className={styles.priceTitle}>פגישת בירור וייעוץ זוגי</h2>
            <div className={styles.priceAmount}>500 ₪</div>
            <p className={styles.priceNote}>
              לפגישה בת 50 דקות מלאות (כולל מע״מ כחוק). דיסקרטיות מלאה, ללא התחייבות מראש להמשך תהליך.
            </p>
          </div>

          <div ref={bookingRef} className={styles.bookingContainer}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>קביעת מועד לפגישה</h2>
              <p className={styles.sectionSubtitle}>
                בחרו את המועד המתאים לכם ביומן לפגישת בירור וייעוץ באשדוד או אונליין בזום.
              </p>
            </div>

            <CalendlyBookingEmbed
              ariaLabel="לוח זמנים לקביעת פגישת בירור וייעוץ זוגי עם שירה סהרוני"
              bookingPagePath="/services/couples/before-separation"
              serviceType="couples_before_separation"
              landingPageType="before_separation"
            />
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>שאלות נפוצות על בירור זוגי לפני החלטות כבדות</h2>
          </div>

          <div className={styles.faqList}>
            {FAQS.map((faq, index) => (
              <div key={faq.q} className={styles.faqItem}>
                <button
                  type="button"
                  className={styles.faqQuestion}
                  onClick={() => toggleFaq(index)}
                  aria-expanded={openFaq === index}
                >
                  <span>{faq.q}</span>
                  {openFaq === index ? <FiChevronUp aria-hidden="true" /> : <FiChevronDown aria-hidden="true" />}
                </button>
                {openFaq === index && (
                  <div className={styles.faqAnswer}>
                    <p>{faq.a}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FINAL CTA Section */}
      <section className={styles.closingCta}>
        <div className="container">
          <h2>לפני שמקבלים החלטה כבדה — עוצרים לבירור רגוע</h2>
          <p>התחלה קצרה ודיסקרטית להבנת המצב והאפשרויות העומדות בפניכם.</p>
          <div className={styles.heroCtaGroup}>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.primaryWhatsappCta}
              onClick={() => {
                trackSecondaryCtaClick('כתבו לי ב-WhatsApp', 'closing_cta');
                trackWhatsappClick();
              }}
            >
              <FaWhatsapp aria-hidden="true" />
              <span>כתבו לי ב-WhatsApp</span>
            </a>
            <button
              type="button"
              className={styles.secondaryBookingCta}
              onClick={() => scrollToBooking('closing_cta')}
            >
              <FiCalendar aria-hidden="true" />
              <span>קביעת פגישת ייעוץ</span>
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className={styles.footer}>
        <div className="container">
          <div className={styles.footerLinks}>
            <a href="/">דף הבית</a>
            <a href="/about">אודות</a>
            <a href="/services/couples">ייעוץ זוגי</a>
            <a href="/services/mediation">גישור</a>
            <a href="/faq">שאלות נפוצות</a>
            <a href="/privacy">מדיניות פרטיות</a>
            <a href="/accessibility">הצהרת נגישות</a>
          </div>
          <p>© {new Date().getFullYear()} שירה סהרוני — קשר. כל הזכויות שמורות.</p>
        </div>
      </footer>

      {/* Mobile Sticky Bar */}
      {!isBookingInView && (
        <div className={styles.mobileStickyBar}>
          <a
            href={whatsappUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.mobileStickyWhatsappBtn}
            onClick={() => {
              trackSecondaryCtaClick('WhatsApp סרגל מובייל', 'mobile_sticky');
              trackWhatsappClick();
            }}
            aria-label="כתבו לי ב-WhatsApp"
          >
            <FaWhatsapp aria-hidden="true" />
            <span>כתבו לי ב-WhatsApp</span>
          </a>
          <button
            type="button"
            className={styles.mobileStickyBtn}
            onClick={() => scrollToBooking('mobile_sticky')}
          >
            <FiCheckCircle aria-hidden="true" />
            <span>קביעת פגישה</span>
          </button>
        </div>
      )}
    </main>
  );
};

export default CouplesBeforeSeparationPage;
