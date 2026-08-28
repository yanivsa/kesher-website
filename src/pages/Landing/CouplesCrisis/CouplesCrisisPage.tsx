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
    q: 'האם חייבים ששני בני הזוג יגיעו?',
    a: 'מומלץ מאוד להגיע כזוג כדי להתחיל מתמונת מצב משותפת. עם זאת, אם בן/בת הזוג מהססים, אפשר להתחיל בפנייה או בשיחת התייעצות ראשונית ב-WhatsApp כדי להבין איך לרתום את שניכם לתהליך.',
  },
  {
    q: 'מה אם אחד מבני הזוג לא רוצה טיפול?',
    a: 'זה מובן ונפוץ מאוד במצבי משבר. אפשר לפנות לשירה ב-WhatsApp להתייעצות קצרה ללא מחויבות, ולקבל כלים איך להציע את המפגש בצורה מזמינה ולא מאיימת.',
  },
  {
    q: 'האם זה מתאים לפני החלטה על פרידה?',
    a: 'כן. ייעוץ זוגי במצב משבר מעניק מרחב בטוח לעצור את ההסלמה, לברר את דפוסי התקשורת ולבחון את האפשרויות לשיקום הקשר לפני קבלת החלטות כבדות.',
  },
  {
    q: 'האם הפגישה דיסקרטית?',
    a: 'בהחלט. כל הפגישות מתקיימות במרחב פרטי, מכבד ודיסקרטי לחלוטין, בהתאם לכללי האתיקה המקצועית.',
  },
  {
    q: 'האם אפשר אונליין?',
    a: 'כן. לצד הפגישות בקליניקה באשדוד, קיימת אפשרות מלאה לקיים פגישות אונליין בזום מכל מקום.',
  },
  {
    q: 'כמה זמן נמשכת פגישה?',
    a: 'פגישת ייעוץ זוגי אורכת 50 דקות מלאות וממוקדות. המחיר הוא 500 ₪ לפגישה, ללא התחייבות מראש לסדרת מפגשים.',
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
    'היי שירה, אנחנו חווים תקופה מורכבת בזוגיות ונשמח לבדוק התאמה לפגישת ייעוץ זוגי.',
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
        name: 'ייעוץ זוגי במצבי משבר',
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
        title="ייעוץ זוגי במשבר | שירה סהרוני – עצירת הסלמה וחידוש התקשורת"
        description="זוגיות במשבר? כשהשיחות חוזרות על עצמן ונגמרות בכעס או בריחוק, אפשר להתחיל משיחה אחת רגועה. ייעוץ זוגי ממוקד ומעשי באשדוד או אונליין. 500 ₪ לפגישה."
        canonical="https://kesher.saharoni.com/services/couples/crisis"
      />
      <SchemaOrg data={schemaData} />

      {/* Minimal Header */}
      <header className={styles.header}>
        <div className={`container ${styles.headerInner}`}>
          <a href="/" className={styles.brand} aria-label="מעבר לדף הבית של שירה סהרוני">
            <img src="/logo-kesher.svg" alt="קשר - שירה סהרוני" className={styles.brandLogo} width="40" height="40" />
            <div className={styles.brandText}>
              <span className={styles.brandTitle}>שירה סהרוני</span>
              <span className={styles.brandSubtitle}>ייעוץ זוגי, הנחיית הורים וגישור</span>
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
              קביעת פגישה
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section (Above the Fold) */}
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
            כשהוויכוחים מתלקחים בשניות, השתיקות הופכות לריחוק והעומס מכריע – לא חייבים להמשיך להסתובב באותו מעגל. ייעוץ זוגי ממוקד ומעשי שמייצר הבנה, בהירות וכלים לתקשורת.
          </p>

          <div className={styles.heroCtaGroup}>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.primaryCta}
              onClick={() => {
                trackCtaClick('כתבו לי ב-WhatsApp', 'hero_primary');
                trackWhatsappClick();
              }}
              aria-label="כתבו לי ב-WhatsApp"
            >
              <FaWhatsapp aria-hidden="true" />
              <span>כתבו לי ב-WhatsApp</span>
            </a>

            <button
              type="button"
              className={styles.secondaryCta}
              onClick={() => scrollToBooking('hero_secondary')}
            >
              <FiCheckCircle aria-hidden="true" />
              <span>קביעת פגישת ייעוץ – 500 ₪</span>
            </button>
          </div>

          <div className={styles.heroTrustRow}>
            <div className={styles.trustItem}>
              <FiMapPin className={styles.trustIcon} aria-hidden="true" />
              <span>אשדוד</span>
            </div>
            <div className={styles.trustItem}>
              <FiClock className={styles.trustIcon} aria-hidden="true" />
              <span>אונליין בזום</span>
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

      {/* Crisis Symptoms Section */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>מתי פונים לייעוץ זוגי ממוקד משבר?</h2>
            <p className={styles.sectionSubtitle}>
              משבר זוגי הוא לא סוף הדרך – לרוב הוא איתות לכך שהדפוסים הישנים כבר אינם משרתים אתכם.
            </p>
          </div>

          <div className={styles.grid3}>
            <div className={styles.painCard}>
              <FiAlertCircle className={styles.painIcon} aria-hidden="true" />
              <h3 className={styles.painTitle}>הסלמה מהירה ופיצוצים</h3>
              <p className={styles.painDesc}>
                נושאים קטנים ביומיום הופכים למריבות קשות, עם תחושה שאף אחד לא מקשיב באמת ושכל מילה הופכת להתקפה.
              </p>
            </div>

            <div className={styles.painCard}>
              <FiMessageSquare className={styles.painIcon} aria-hidden="true" />
              <h3 className={styles.painTitle}>שתיקות, ריחוק וניתוק</h3>
              <p className={styles.painDesc}>
                ויתור על שיחות עומק, הליכה "על ביצים", תחושת בדידות עמוקה בתוך הבית וחיים כשותפים לדירה בלבד.
              </p>
            </div>

            <div className={styles.painCard}>
              <FiHeart className={styles.painIcon} aria-hidden="true" />
              <h3 className={styles.painTitle}>עומס הורים ושחיקה</h3>
              <p className={styles.painDesc}>
                הילדים, הקריירה והלחצים הכלכליים דוחקים את הזוגיות לתחתית סדר העדיפויות, עד שלא נשאר כוח אחד לשני.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 3 Step Approach */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>איך נראה התהליך בפועל?</h2>
            <p className={styles.sectionSubtitle}>
              גישה מובנית, מכבדת ומעשית שנועדה לתת מענה מידי ולאפשר שינוי הדרגתי ויציב.
            </p>
          </div>

          <div className={styles.stepsGrid}>
            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>1</div>
              <h3 className={styles.stepTitle}>פגישת מיפוי והיכרות</h3>
              <p className={styles.stepDesc}>
                הבנת מוקדי החיכוך, זיהוי נקודות ההסלמה והגדרת הצרכים המרכזיים של כל אחד מכם במרחב רגוע ולא שיפוטי.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>2</div>
              <h3 className={styles.stepTitle}>עצירת דפוסי הפגיעה</h3>
              <p className={styles.stepDesc}>
                רכישת כלים מידיים לשיח אחר: איך לעצור ויכוח לפני שהוא מתפוצץ, איך להקשיב בלי להתגונן ואיך לבטא צורך בלי להאשים.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>3</div>
              <h3 className={styles.stepTitle}>בניית הסכמות וחידוש הקשר</h3>
              <p className={styles.stepDesc}>
                קביעת הסכמות יומיומיות סביב חלוקת עומסים, הורות וזמן זוגי, שמאפשרות להחזיר את האמון והקרבה לקשר.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Bio Section */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.bioCard}>
            <div className={styles.bioHeader}>
              <img
                src="/images/shira-profile.jpg"
                alt="שירה סהרוני - יועצת זוגית ומגשרת מוסמכת"
                className={styles.bioAvatar}
                width="90"
                height="90"
                loading="lazy"
              />
              <div>
                <h2 className={styles.bioName}>שירה סהרוני</h2>
                <p className={styles.bioRole}>יועצת זוגית, מנחת הורים ומגשרת מוסמכת</p>
              </div>
            </div>

            <p className={styles.bioText}>
              עורכת דין בהכשרתה שבחרה להקדיש את פעילותה המקצועית לליווי זוגות ומשפחות. הגישה שלי משלבת הקשבה אמפתית, ראייה מערכתית וכלים מובנים ליצירת שיח בונה. אני מאמינה שגם במשברים עמוקים, כשיש מרחב בטוח ומכוון, אפשר למצוא מחדש את הדרך אחד אל השני.
            </p>

            <div className={styles.credentialsList}>
              <span className={styles.credentialPill}>✓ יועצת זוגית מוסמכת</span>
              <span className={styles.credentialPill}>✓ מנחת הורים מוסמכת</span>
              <span className={styles.credentialPill}>✓ מגשרת מוסמכת</span>
              <span className={styles.credentialPill}>✓ עורכת דין בהכשרתה</span>
              <span className={styles.credentialPill}>✓ קליניקה באשדוד ובזום</span>
            </div>
          </div>
        </div>
      </section>

      {/* Transparent Pricing Card */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.priceCard}>
            <h2 className={styles.priceTitle}>פגישת ייעוץ זוגי ממוקדת</h2>
            <div className={styles.priceAmount}>500 ₪</div>
            <p className={styles.priceNote}>
              לפגישה בת 50 דקות מלאות (כולל מע״מ כחוק). ללא תשלום מראש וללא התחייבות לסדרת מפגשים.
            </p>
          </div>

          {/* Booking Embed Section */}
          <div ref={bookingRef} className={styles.bookingContainer}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>קביעת מועד לפגישה</h2>
              <p className={styles.sectionSubtitle}>
                בחרו את המועד המתאים לכם ביומן לקביעת פגישה בקליניקה באשדוד או אונליין בזום.
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
            <h2 className={styles.sectionTitle}>שאלות נפוצות על ייעוץ זוגי</h2>
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

      {/* Minimal Footer */}
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
          <p>© {new Date().getFullYear()} שירה סהרוני. כל הזכויות שמורות.</p>
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
            aria-label="הודעה ב-WhatsApp לשירה סהרוני"
          >
            <FaWhatsapp aria-hidden="true" />
            <span>WhatsApp</span>
          </a>
          <button
            type="button"
            className={styles.mobileStickyBtn}
            onClick={() => scrollToBooking('mobile_sticky')}
          >
            <FiCheckCircle aria-hidden="true" />
            <span>קביעת פגישה – 500 ₪</span>
          </button>
        </div>
      )}
    </main>
  );
};

export default CouplesCrisisPage;
