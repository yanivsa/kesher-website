import React, { useState, useEffect, useRef } from 'react';
import {
  FiClock,
  FiShield,
  FiMapPin,
  FiCheckCircle,
  FiAlertCircle,
  FiMessageSquare,
  FiHeart,
  FiPhone,
  FiChevronDown,
  FiChevronUp,
  FiCalendar,
  FiUserCheck,
} from 'react-icons/fi';
import { FaWhatsapp } from 'react-icons/fa';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import CalendlyBookingEmbed from '../../../components/Booking/CalendlyBookingEmbed';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import { useLandingPageAnalytics } from '../../../hooks/useLandingPageAnalytics';
import styles from './CouplesCrisisPage.module.css';

interface FAQItem {
  q: string;
  a: string;
}

const FAQS: FAQItem[] = [
  {
    q: 'האם חייבים ששני בני הזוג יגיעו לפגישה הראשונה?',
    a: 'מומלץ מאוד להגיע יחד כדי להתחיל מתמונת מצב משותפת. עם זאת, אם בן או בת הזוג חוששים או מתלבטים, ניתן להתחיל מפגישת היכרות קצרה או לכתוב לשירה ב-WhatsApp להתייעצות לפני הקביעה.',
  },
  {
    q: 'מה אם אחד מבני הזוג לא רוצה טיפול או מיואש?',
    a: 'חשש או שחיקה הם טבעיים במצבי משבר. התהליך בחדר הייעוץ אינו מיועד לשפוט, להאשים או לקבוע מי צודק, אלא להאט את המתח, להבין איפה השיחה מסתבכת ולבדוק האם קיימת דרך מועילה יותר לתקשר.',
  },
  {
    q: 'האם זה מתאים גם לפני החלטה על פרידה?',
    a: 'כן. לפני שמקבלים החלטות כבדות או מפרקים את הקשר, בירור זוגי רגוע מאפשר להבין לעומק מה קורה ביניכם, לבחון אם ומה ניתן לשנות, ולהגיע להחלטות שקולות ואחראיות.',
  },
  {
    q: 'האם הפגישה דיסקרטית?',
    a: 'בהחלט. כל פגישה מתקיימת במרחב פרטי, בטוח ומכבד בדיסקרטיות מלאה בהתאם לכללי האתיקה המקצועית.',
  },
  {
    q: 'האם אפשר לקיים את הפגישה אונליין?',
    a: 'כן. לצד הקליניקה באשדוד, ניתן לקיים את פגישות הייעוץ אונליין בזום (Zoom) מכל מקום בארץ ובעולם.',
  },
  {
    q: 'כמה זמן נמשכת פגישה ומה המחיר?',
    a: 'פגישת ייעוץ זוגי אורכת 50 דקות מלאות וממוקדות. העלות היא 500 ₪ כולל מע״מ לפגישה, ללא התחייבות מראש לסדרת מפגשים.',
  },
];

const CouplesCrisisPage: React.FC = () => {
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
    landingPagePath: '/services/couples/crisis',
    landingPageType: 'crisis',
    serviceType: 'couples_crisis',
  });

  const whatsappPhone = SITE_CONFIG.contact.phone.replace(/[^0-9]/g, '');
  const whatsappUrl = `https://wa.me/${whatsappPhone}?text=${encodeURIComponent(
    'היי שירה, אנחנו חווים תקופה מורכבת בזוגיות ונשמח להתייעץ בדיסקרטיות.',
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
        name: 'ייעוץ זוגי במצבי משבר | שירה סהרוני',
        serviceType: 'Couples Crisis Counseling',
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
        title="זוגיות במשבר | שירה סהרוני – ייעוץ זוגי מעשי באשדוד ובאונליין"
        description="זוגיות במשבר? כשהוויכוחים מתלקחים בשניות והשתיקות מעמיקות, אפשר להתחיל משיחה אחת רגועה. ייעוץ זוגי ממוקד באשדוד או אונליין. 50 דקות, 500 ₪."
        canonical="https://kesher.saharoni.com/services/couples/crisis"
      />
      <SchemaOrg data={schemaData} />

      {/* Header */}
      <header className={styles.header}>
        <div className={`container ${styles.headerInner}`}>
          <a href="/" className={styles.brand} aria-label="מעבר לדף הבית של שירה סהרוני">
            <img src="/logo-kesher.svg" alt="קשר - שירה סהרוני" className={styles.brandLogo} width="40" height="40" />
            <div className={styles.brandText}>
              <span className={styles.brandTitle}>שירה סהרוני</span>
              <span className={styles.brandSubtitle}>ייעוץ זוגי במשבר | אשדוד ואונליין</span>
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
            <FiAlertCircle aria-hidden="true" />
            <span>מרחב בטוח לעצירת ההסלמה והחזרת השקט</span>
          </div>

          <h1 className={styles.heroTitle}>
            זוגיות במשבר? אפשר להתחיל משיחה אחת רגועה
          </h1>

          <p className={styles.heroSubtitle}>
            כשהוויכוחים מתלקחים בשניות, השתיקות הופכות לריחוק ואובדן האמון מעמיק — לא חייבים להמשיך להסתובב באותו מעגל שוחק. ייעוץ זוגי ממוקד ומעשי לעצירת ההסלמה, הבנת הדפוס ולמידת דרך אחרת לדבר.
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
            <h2 className={styles.sectionTitle}>איך נראה משבר בזוגיות?</h2>
            <p className={styles.sectionSubtitle}>
              משבר זוגי נוצר כשהדפוסים הישנים מפסיקים לעבוד, והתקשורת הופכת למאבק שוחק או לריחוק כואב.
            </p>
          </div>

          <div className={styles.grid3}>
            <div className={styles.painCard}>
              <FiAlertCircle className={styles.painIcon} aria-hidden="true" />
              <h3 className={styles.painTitle}>הסלמה מהירה ופיצוצים</h3>
              <p className={styles.painDesc}>
                נושאים קטנים ביומיום הופכים מהר מאוד למריבות קשות, מלווים בתחושה שאף אחד לא מקשיב באמת ושכל מילה נתפסת כביקורת.
              </p>
            </div>

            <div className={styles.painCard}>
              <FiMessageSquare className={styles.painIcon} aria-hidden="true" />
              <h3 className={styles.painTitle}>שתיקות, ריחוק ואובדן אמון</h3>
              <p className={styles.painDesc}>
                הימנעות משיחות עומק, הליכה "על ביצים", תחושת בדידות עמוקה בתוך הבית וספקות גוברים לגבי עתיד הקשר.
              </p>
            </div>

            <div className={styles.painCard}>
              <FiHeart className={styles.painIcon} aria-hidden="true" />
              <h3 className={styles.painTitle}>עייפות ושחיקה מתמשכת</h3>
              <p className={styles.painDesc}>
                עומס משימות הבית והילדים דוחק את היחסים לתחתית הסדר, עד שנגמר הכוח לנסות ולדבר שוב.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* SOLUTION Section */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>הפתרון: עצירת ההסלמה ובניית שיח חדש</h2>
            <p className={styles.sectionSubtitle}>
              תהליך ממוקד המאפשר להבין את המנגנון שמפעיל את הריב, לנטרל את ההתגוננות ולצאת עם צעד מעשי אחד.
            </p>
          </div>

          <div className={styles.stepsGrid}>
            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>1</div>
              <h3 className={styles.stepTitle}>מיפוי דפוס השיחה</h3>
              <p className={styles.stepDesc}>
                מבינים איפה השיחה נתקעת, מה גורם לאחד להתגונן ולשני להתרחק, בלי לבחור צדדים ובלי לחפש מי אשם.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>2</div>
              <h3 className={styles.stepTitle}>הפחתת מתח ועצירת הסלמה</h3>
              <p className={styles.stepDesc}>
                רוכשים כלים מעשיים לעצירת התדרדרות השיחה בזמן אמת ולהקשבה מכבדת גם כשקיימת מחלוקת.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>3</div>
              <h3 className={styles.stepTitle}>צעד מעשי ראשון לבית</h3>
              <p className={styles.stepDesc}>
                יוצאים מהפגישה הראשונה עם כלי מוגדר אחד לתרגול יומיומי בבית להחזרת השקט והביטחון ביחסים.
              </p>
            </div>
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
              הגישה המקצועית שלי משלבת הקשבה בגובה העיניים, ראייה מערכתית וכלים מעשיים وتקשורתיים. אני פוגשת זוגות ברגעי עומס ומשבר ומסייעת להם לעשות סדר, להפחית הסלמה ולהחזיר את האמון והקרבה.
            </p>

            <div className={styles.credentialsList}>
              <span className={styles.credentialPill}>✓ יועצת זוגית מוסמכת</span>
              <span className={styles.credentialPill}>✓ מנחת הורים מוסמכת</span>
              <span className={styles.credentialPill}>✓ מגשרת מוסמכת</span>
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
            <h2 className={styles.priceTitle}>פגישת ייעוץ זוגי במצב משבר</h2>
            <div className={styles.priceAmount}>500 ₪</div>
            <p className={styles.priceNote}>
              לפגישה בת 50 דקות מלאות (כולל מע״מ כחוק). דיסקרטיות מלאה, ללא התחייבות לסדרת טיפולים מראש.
            </p>
          </div>

          <div ref={bookingRef} className={styles.bookingContainer}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>קביעת מועד לפגישה</h2>
              <p className={styles.sectionSubtitle}>
                בחרו את המועד המתאים לכם ביומן לפגישה בקליניקה באשדוד או אונליין בזום.
              </p>
            </div>

            <CalendlyBookingEmbed
              ariaLabel="לוח זמנים לקביעת פגישת ייעוץ זוגי עם שירה סהרוני"
              bookingPagePath="/services/couples/crisis"
              serviceType="couples_crisis"
              landingPageType="crisis"
            />
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>שאלות נפוצות על ייעוץ זוגי במשבר</h2>
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
          <h2>אפשר להחזיר את השקט והביטחון ליחסים</h2>
          <p>התחלה קצרה ודיסקרטית משיחה אחת ממוקדת.</p>
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

export default CouplesCrisisPage;
